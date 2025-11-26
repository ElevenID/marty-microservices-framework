"""
Database Adapter
"""

import logging
import time
from typing import Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from mmf_new.framework.integration.ports.connector import ExternalSystemPort
from mmf_new.framework.integration.domain.models import (
    ConnectionConfig,
    IntegrationRequest,
    IntegrationResponse,
)
from mmf_new.framework.integration.domain.exceptions import ConnectionFailedError

class DatabaseAdapter(ExternalSystemPort):
    """Database connector implementation using SQLAlchemy AsyncIO."""

    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.engine = None
        self.session_factory = None
        self.connected = False

    async def connect(self) -> bool:
        """Establish database connection."""
        try:
            connection_string = self.config.endpoint_url
            if not connection_string:
                raise ValueError("No connection string provided")

            # Ensure async driver is used (e.g., postgresql+asyncpg)
            if "postgresql://" in connection_string:
                connection_string = connection_string.replace("postgresql://", "postgresql+asyncpg://")

            self.engine = create_async_engine(
                connection_string,
                pool_size=self.config.protocol_settings.get("pool_size", 5),
                max_overflow=self.config.protocol_settings.get("max_overflow", 10),
                pool_pre_ping=True,
                echo=False,
            )

            # Test connection
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

            self.session_factory = async_sessionmaker(bind=self.engine, expire_on_commit=False)
            logging.info(f"Connected to database: {self.config.endpoint_url}")
            self.connected = True
            return True
        except Exception as e:
            logging.exception(f"Failed to connect to database: {e}")
            raise ConnectionFailedError(f"Failed to connect: {e}")

    async def disconnect(self) -> bool:
        """Close database connection."""
        try:
            if self.engine:
                await self.engine.dispose()
                self.engine = None
                self.session_factory = None
            self.connected = False
            logging.info(f"Disconnected from database: {self.config.endpoint_url}")
            return True
        except Exception as e:
            logging.exception(f"Failed to disconnect from database: {e}")
            return False

    async def execute_request(self, request: IntegrationRequest) -> IntegrationResponse:
        """Execute database query."""
        if not self.engine:
            await self.connect()

        start_time = time.time()
        
        try:
            query = request.data.get("query") if isinstance(request.data, dict) else str(request.data)
            params = request.data.get("params", {}) if isinstance(request.data, dict) else {}
            
            if not query:
                raise ValueError("No query provided")

            if not self.session_factory:
                raise ConnectionFailedError("Database not connected")

            async with self.session_factory() as session:
                result = await session.execute(text(query), params)
                
                # Commit if it's a modification
                if request.operation.lower() in ["insert", "update", "delete"]:
                    await session.commit()
                    data = {"rows_affected": getattr(result, "rowcount", -1)}
                else:
                    # Fetch results for SELECT
                    try:
                        rows = result.fetchall()
                        # Convert rows to dicts if possible, or list of values
                        if result.keys():
                            keys = list(result.keys())
                            data = [dict(zip(keys, row)) for row in rows]
                        else:
                            data = [list(row) for row in rows]
                    except Exception:
                        data = {"status": "executed"}

            latency = (time.time() - start_time) * 1000
            return IntegrationResponse(
                request_id=request.request_id,
                success=True,
                data=data,
                latency_ms=latency
            )
            
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return IntegrationResponse(
                request_id=request.request_id,
                success=False,
                data=None,
                error_message=str(e),
                latency_ms=latency
            )

    async def health_check(self) -> bool:
        """Check health of database."""
        if not self.engine:
            return False
            
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
