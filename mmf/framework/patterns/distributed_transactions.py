"""
Distributed Transactions Implementation for Marty Microservices Framework

This module implements distributed transaction patterns including two-phase commit,
transaction coordination, and distributed transaction management.
"""

import asyncio
import builtins
import logging
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TransactionState(Enum):
    """Distributed transaction states."""

    STARTED = "started"
    PREPARING = "preparing"
    PREPARED = "prepared"
    COMMITTING = "committing"
    COMMITTED = "committed"
    ABORTING = "aborting"
    ABORTED = "aborted"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class TransactionParticipant:
    """Participant in distributed transaction."""

    participant_id: str
    service_name: str
    endpoint: str
    state: TransactionState = TransactionState.STARTED
    prepared_at: datetime | None = None
    committed_at: datetime | None = None
    aborted_at: datetime | None = None


@dataclass
class DistributedTransaction:
    """Distributed transaction definition."""

    transaction_id: str
    coordinator_id: str
    participants: builtins.list[TransactionParticipant]
    state: TransactionState = TransactionState.STARTED
    timeout_seconds: int = 300  # 5 minutes default
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: builtins.dict[str, Any] = field(default_factory=dict)


class DistributedTransactionCoordinator:
    """Coordinates distributed transactions using 2PC protocol."""

    def __init__(self, coordinator_id: str, timeout_seconds: int = 300):
        """Initialize transaction coordinator."""
        self.coordinator_id = coordinator_id
        self.timeout_seconds = timeout_seconds
        self.transactions: builtins.dict[str, DistributedTransaction] = {}
        self.lock = threading.RLock()

        # Background tasks
        self.cleanup_task: asyncio.Task | None = None
        self.is_running = False

    async def start(self):
        """Start coordinator background tasks."""
        if self.is_running:
            return

        self.is_running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logging.info("Transaction coordinator started: %s", self.coordinator_id)

    async def stop(self):
        """Stop coordinator background tasks."""
        if not self.is_running:
            return

        self.is_running = False

        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

        logging.info("Transaction coordinator stopped: %s", self.coordinator_id)

    async def begin_transaction(
        self,
        participants: builtins.list[builtins.dict[str, str]],
        context: builtins.dict[str, Any] | None = None,
    ) -> str:
        """Begin a new distributed transaction."""
        transaction_id = str(uuid.uuid4())

        # Create participant objects
        transaction_participants = []
        for participant_data in participants:
            participant = TransactionParticipant(
                participant_id=str(uuid.uuid4()),
                service_name=participant_data["service_name"],
                endpoint=participant_data["endpoint"],
            )
            transaction_participants.append(participant)

        # Create transaction
        transaction = DistributedTransaction(
            transaction_id=transaction_id,
            coordinator_id=self.coordinator_id,
            participants=transaction_participants,
            context=context or {},
        )

        with self.lock:
            self.transactions[transaction_id] = transaction

        logging.info("Started distributed transaction: %s", transaction_id)
        return transaction_id

    async def prepare_transaction(self, transaction_id: str) -> bool:
        """Prepare phase of 2PC protocol."""
        with self.lock:
            transaction = self.transactions.get(transaction_id)
            if not transaction:
                return False

            if transaction.state != TransactionState.STARTED:
                return False

            transaction.state = TransactionState.PREPARING
            transaction.updated_at = datetime.now(timezone.utc)

        # Prepare each participant
        prepare_results = []
        for participant in transaction.participants:
            try:
                # In a real implementation, this would make HTTP calls
                # to participant services
                result = await self._prepare_participant(transaction_id, participant)
                prepare_results.append(result)

                if result:
                    participant.state = TransactionState.PREPARED
                    participant.prepared_at = datetime.now(timezone.utc)
                else:
                    participant.state = TransactionState.FAILED

            except Exception as e:
                logging.exception(
                    "Prepare failed for participant %s: %s", participant.participant_id, e
                )
                participant.state = TransactionState.FAILED
                prepare_results.append(False)

        # Update transaction state
        with self.lock:
            if all(prepare_results):
                transaction.state = TransactionState.PREPARED
            else:
                transaction.state = TransactionState.FAILED

            transaction.updated_at = datetime.now(timezone.utc)

        return transaction.state == TransactionState.PREPARED

    async def commit_transaction(self, transaction_id: str) -> bool:
        """Commit phase of 2PC protocol."""
        with self.lock:
            transaction = self.transactions.get(transaction_id)
            if not transaction:
                return False

            if transaction.state != TransactionState.PREPARED:
                return False

            transaction.state = TransactionState.COMMITTING
            transaction.updated_at = datetime.now(timezone.utc)

        # Commit each participant
        commit_results = []
        for participant in transaction.participants:
            try:
                # In a real implementation, this would make HTTP calls
                # to participant services
                result = await self._commit_participant(transaction_id, participant)
                commit_results.append(result)

                if result:
                    participant.state = TransactionState.COMMITTED
                    participant.committed_at = datetime.now(timezone.utc)
                else:
                    participant.state = TransactionState.FAILED

            except Exception as e:
                logging.exception(
                    "Commit failed for participant %s: %s", participant.participant_id, e
                )
                participant.state = TransactionState.FAILED
                commit_results.append(False)

        # Update transaction state
        with self.lock:
            if all(commit_results):
                transaction.state = TransactionState.COMMITTED
            else:
                transaction.state = TransactionState.FAILED

            transaction.updated_at = datetime.now(timezone.utc)

        return transaction.state == TransactionState.COMMITTED

    async def abort_transaction(self, transaction_id: str) -> bool:
        """Abort transaction and rollback participants."""
        with self.lock:
            transaction = self.transactions.get(transaction_id)
            if not transaction:
                return False

            if transaction.state in [TransactionState.COMMITTED, TransactionState.ABORTED]:
                return transaction.state == TransactionState.ABORTED

            transaction.state = TransactionState.ABORTING
            transaction.updated_at = datetime.now(timezone.utc)

        # Abort each participant
        abort_results = []
        for participant in transaction.participants:
            try:
                # Only abort if participant was prepared
                if participant.state == TransactionState.PREPARED:
                    result = await self._abort_participant(transaction_id, participant)
                    abort_results.append(result)

                    if result:
                        participant.state = TransactionState.ABORTED
                        participant.aborted_at = datetime.now(timezone.utc)
                    else:
                        participant.state = TransactionState.FAILED
                else:
                    abort_results.append(True)  # Nothing to abort

            except Exception as e:
                logging.exception(
                    "Abort failed for participant %s: %s", participant.participant_id, e
                )
                participant.state = TransactionState.FAILED
                abort_results.append(False)

        # Update transaction state
        with self.lock:
            if all(abort_results):
                transaction.state = TransactionState.ABORTED
            else:
                transaction.state = TransactionState.FAILED

            transaction.updated_at = datetime.now(timezone.utc)

        return transaction.state == TransactionState.ABORTED

    async def get_transaction_status(self, transaction_id: str) -> TransactionState | None:
        """Get current transaction status."""
        with self.lock:
            transaction = self.transactions.get(transaction_id)
            return transaction.state if transaction else None

    async def get_transaction(self, transaction_id: str) -> DistributedTransaction | None:
        """Get transaction details."""
        with self.lock:
            return self.transactions.get(transaction_id)

    async def _prepare_participant(
        self, transaction_id: str, participant: TransactionParticipant
    ) -> bool:
        """Prepare individual participant (mock implementation)."""
        # In a real implementation, this would make HTTP call to participant
        # For now, simulate success/failure
        await asyncio.sleep(0.1)  # Simulate network delay
        return True  # Mock success

    async def _commit_participant(
        self, transaction_id: str, participant: TransactionParticipant
    ) -> bool:
        """Commit individual participant (mock implementation)."""
        # In a real implementation, this would make HTTP call to participant
        await asyncio.sleep(0.1)  # Simulate network delay
        return True  # Mock success

    async def _abort_participant(
        self, transaction_id: str, participant: TransactionParticipant
    ) -> bool:
        """Abort individual participant (mock implementation)."""
        # In a real implementation, this would make HTTP call to participant
        await asyncio.sleep(0.1)  # Simulate network delay
        return True  # Mock success

    async def _cleanup_loop(self):
        """Background task to clean up expired transactions."""
        while self.is_running:
            try:
                await self._cleanup_expired_transactions()
                await asyncio.sleep(60)  # Run every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.exception("Cleanup loop error: %s", e)
                await asyncio.sleep(60)

    async def _cleanup_expired_transactions(self):
        """Clean up expired transactions."""
        now = datetime.now(timezone.utc)
        expired_transactions = []

        with self.lock:
            for transaction_id, transaction in self.transactions.items():
                # Check if transaction has expired
                elapsed = (now - transaction.created_at).total_seconds()
                if elapsed > transaction.timeout_seconds:
                    if transaction.state not in [
                        TransactionState.COMMITTED,
                        TransactionState.ABORTED,
                    ]:
                        expired_transactions.append(transaction_id)

        # Abort expired transactions
        for transaction_id in expired_transactions:
            logging.warning("Aborting expired transaction: %s", transaction_id)
            await self.abort_transaction(transaction_id)

            # Mark as timeout
            with self.lock:
                transaction = self.transactions.get(transaction_id)
                if transaction:
                    transaction.state = TransactionState.TIMEOUT
                    transaction.updated_at = now

    def get_transaction_statistics(self) -> builtins.dict[str, Any]:
        """Get transaction statistics."""
        with self.lock:
            stats = {
                "total_transactions": len(self.transactions),
                "by_state": defaultdict(int),
                "coordinator_id": self.coordinator_id,
            }

            for transaction in self.transactions.values():
                stats["by_state"][transaction.state.value] += 1

            return dict(stats)


class TransactionManager:
    """High-level transaction manager."""

    def __init__(self, coordinator: DistributedTransactionCoordinator):
        """Initialize transaction manager."""
        self.coordinator = coordinator

    async def execute_transaction(
        self,
        participants: builtins.list[builtins.dict[str, str]],
        context: builtins.dict[str, Any] | None = None,
    ) -> builtins.dict[str, Any]:
        """Execute a complete distributed transaction."""
        # Begin transaction
        transaction_id = await self.coordinator.begin_transaction(participants, context)

        try:
            # Prepare phase
            prepare_success = await self.coordinator.prepare_transaction(transaction_id)

            if prepare_success:
                # Commit phase
                commit_success = await self.coordinator.commit_transaction(transaction_id)

                if commit_success:
                    return {
                        "transaction_id": transaction_id,
                        "status": "committed",
                        "success": True,
                    }
                else:
                    # Commit failed, abort
                    await self.coordinator.abort_transaction(transaction_id)
                    return {
                        "transaction_id": transaction_id,
                        "status": "failed_commit",
                        "success": False,
                    }
            else:
                # Prepare failed, abort
                await self.coordinator.abort_transaction(transaction_id)
                return {
                    "transaction_id": transaction_id,
                    "status": "failed_prepare",
                    "success": False,
                }

        except Exception as e:
            logging.exception("Transaction execution error: %s", e)
            await self.coordinator.abort_transaction(transaction_id)
            return {
                "transaction_id": transaction_id,
                "status": "error",
                "success": False,
                "error": str(e),
            }
