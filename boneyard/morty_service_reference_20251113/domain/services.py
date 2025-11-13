"""
Domain services for Morty service.

Domain services contain business logic that doesn't naturally fit within entities or value objects.
They coordinate between multiple entities and enforce business rules that span multiple objects.
"""

import builtins
from datetime import datetime

from .entities import Task, User
from .events import TaskAssigned, TaskCompleted, TaskCreated


class TaskManagementService:
    """Domain service for managing task-related business operations."""

    def __init__(self):
        self._events: builtins.list = []

    def create_task(
        self,
        title: str,
        description: str,
        priority: str = "medium",
        assignee: User | None = None,
    ) -> Task:
        """Create a new task with proper validation and event generation."""

        # Create the task
        task = Task(title=title, description=description, priority=priority, assignee=assignee)

        # Generate domain event
        event = TaskCreated(
            task_id=task.id,
            title=task.title,
            priority=task.priority,
            assignee_id=assignee.id if assignee else None,
            occurred_at=datetime.utcnow(),
        )
        self._events.append(event)

        return task

    def assign_task(self, task: Task, assignee: User) -> None:
        """Assign a task to a user with proper business rules."""

        if not assignee.active:
            raise ValueError("Cannot assign task to inactive user")

        # Check if user has too many pending tasks
        pending_tasks = assignee.get_pending_tasks()
        if len(pending_tasks) >= 10:  # Business rule: max 10 pending tasks
            raise ValueError("User has too many pending tasks")

        # Perform the assignment
        old_assignee_id = task.assignee.id if task.assignee else None
        task.assign_to(assignee)
        assignee.add_task(task)

        # Generate domain event
        event = TaskAssigned(
            task_id=task.id,
            assignee_id=assignee.id,
            previous_assignee_id=old_assignee_id,
            occurred_at=datetime.utcnow(),
        )
        self._events.append(event)

    def complete_task(self, task: Task) -> None:
        """Complete a task with proper validation."""

        if task.status == "completed":
            raise ValueError("Task is already completed")

        if not task.assignee:
            raise ValueError("Cannot complete task without assignee")

        # Mark as completed
        task.mark_completed()

        # Generate domain event
        event = TaskCompleted(
            task_id=task.id,
            assignee_id=task.assignee.id,
            completed_at=task.completed_at,
            occurred_at=datetime.utcnow(),
        )
        self._events.append(event)

    def prioritize_tasks(self, tasks: builtins.list[Task]) -> builtins.list[Task]:
        """Sort tasks by priority and creation date."""

        def priority_sort_key(task: Task) -> tuple:
            priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
            return (priority_order.get(task.priority, 3), task.created_at)

        return sorted(tasks, key=priority_sort_key)

    def get_pending_events(self) -> builtins.list:
        """Get all pending domain events."""
        return self._events.copy()

    def clear_events(self) -> None:
        """Clear all pending events (typically called after publishing)."""
        self._events.clear()


class UserManagementService:
    """Domain service for managing user-related business operations."""

    def __init__(self):
        self._events: builtins.list = []

    def calculate_user_workload(self, user: User) -> dict:
        """Calculate workload metrics for a user."""

        pending_tasks = user.get_pending_tasks()
        completed_tasks = user.get_completed_tasks()

        # Calculate priority distribution
        priority_counts = {"low": 0, "medium": 0, "high": 0, "urgent": 0}
        for task in pending_tasks:
            priority_counts[task.priority] += 1

        # Calculate workload score (weighted by priority)
        workload_score = (
            priority_counts["low"] * 1
            + priority_counts["medium"] * 2
            + priority_counts["high"] * 3
            + priority_counts["urgent"] * 5
        )

        return {
            "user_id": user.id,
            "pending_task_count": len(pending_tasks),
            "completed_task_count": len(completed_tasks),
            "priority_distribution": priority_counts,
            "workload_score": workload_score,
            "is_overloaded": workload_score > 20,  # Business rule threshold
        }

    def find_best_assignee(self, users: builtins.list[User], task_priority: str) -> User | None:
        """Find the best user to assign a task to based on workload and availability."""

        # Filter active users only
        active_users = [user for user in users if user.active]

        if not active_users:
            return None

        # Calculate workload for each user
        user_workloads = []
        for user in active_users:
            workload = self.calculate_user_workload(user)
            if not workload["is_overloaded"]:  # Only consider non-overloaded users
                user_workloads.append((user, workload))

        if not user_workloads:
            return None  # All users are overloaded

        # Sort by workload score (ascending - prefer users with less work)
        user_workloads.sort(key=lambda x: x[1]["workload_score"])

        return user_workloads[0][0]

    def get_pending_events(self) -> builtins.list:
        """Get all pending domain events."""
        return self._events.copy()

    def clear_events(self) -> None:
        """Clear all pending events."""
        self._events.clear()
