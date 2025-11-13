"""
HTTP adapter for the Morty service.

This adapter implements a FastAPI-based REST API that serves as an input adapter,
implementing the input ports defined in the application layer.
"""

import builtins
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ...application.ports.input_ports import (
    AssignTaskCommand,
    CreateTaskCommand,
    CreateUserCommand,
    TaskDTO,
    TaskManagementPort,
    UpdateTaskCommand,
    UserDTO,
    UserManagementPort,
    UserWorkloadDTO,
)


# Pydantic models for API serialization
class CreateTaskRequest(BaseModel):
    """Request model for creating a task."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    priority: str = Field("medium", regex="^(low|medium|high|urgent)$")
    assignee_id: UUID | None = None


class UpdateTaskRequest(BaseModel):
    """Request model for updating a task."""

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, min_length=1)
    priority: str | None = Field(None, regex="^(low|medium|high|urgent)$")


class AssignTaskRequest(BaseModel):
    """Request model for assigning a task."""

    assignee_id: UUID


class CreateUserRequest(BaseModel):
    """Request model for creating a user."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., regex=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    phone: str | None = None


class TaskResponse(BaseModel):
    """Response model for task data."""

    id: UUID
    title: str
    description: str
    priority: str
    status: str
    assignee_id: UUID | None
    assignee_name: str | None
    created_at: str
    updated_at: str
    completed_at: str | None = None

    @classmethod
    def from_dto(cls, dto: TaskDTO) -> "TaskResponse":
        return cls(
            id=dto.id,
            title=dto.title,
            description=dto.description,
            priority=dto.priority,
            status=dto.status,
            assignee_id=dto.assignee_id,
            assignee_name=dto.assignee_name,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
            completed_at=dto.completed_at,
        )


class UserResponse(BaseModel):
    """Response model for user data."""

    id: UUID
    first_name: str
    last_name: str
    email: str
    phone: str | None
    active: bool
    pending_task_count: int
    completed_task_count: int
    created_at: str
    updated_at: str

    @classmethod
    def from_dto(cls, dto: UserDTO) -> "UserResponse":
        return cls(
            id=dto.id,
            first_name=dto.first_name,
            last_name=dto.last_name,
            email=dto.email,
            phone=dto.phone,
            active=dto.active,
            pending_task_count=dto.pending_task_count,
            completed_task_count=dto.completed_task_count,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )


class UserWorkloadResponse(BaseModel):
    """Response model for user workload data."""

    user_id: UUID
    pending_task_count: int
    completed_task_count: int
    workload_score: int
    is_overloaded: bool
    priority_distribution: dict

    @classmethod
    def from_dto(cls, dto: UserWorkloadDTO) -> "UserWorkloadResponse":
        return cls(
            user_id=dto.user_id,
            pending_task_count=dto.pending_task_count,
            completed_task_count=dto.completed_task_count,
            workload_score=dto.workload_score,
            is_overloaded=dto.is_overloaded,
            priority_distribution=dto.priority_distribution,
        )


class HTTPAdapter:
    """HTTP adapter implementing the REST API for Morty service."""

    def __init__(
        self,
        task_management: TaskManagementPort,
        user_management: UserManagementPort,
    ):
        self._task_management = task_management
        self._user_management = user_management
        self._router = APIRouter()
        self._setup_routes()

    @property
    def router(self) -> APIRouter:
        """Get the FastAPI router."""
        return self._router

    def _setup_routes(self) -> None:
        """Setup all HTTP routes."""

        # Task routes
        @self._router.post(
            "/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED
        )
        async def create_task(request: CreateTaskRequest) -> TaskResponse:
            """Create a new task."""
            try:
                command = CreateTaskCommand(
                    title=request.title,
                    description=request.description,
                    priority=request.priority,
                    assignee_id=request.assignee_id,
                )
                task_dto = await self._task_management.create_task(command)
                return TaskResponse.from_dto(task_dto)
            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        @self._router.get("/tasks/{task_id}", response_model=TaskResponse)
        async def get_task(task_id: UUID) -> TaskResponse:
            """Get a task by its ID."""
            task_dto = await self._task_management.get_task(task_id)
            if not task_dto:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
            return TaskResponse.from_dto(task_dto)

        @self._router.put("/tasks/{task_id}", response_model=TaskResponse)
        async def update_task(task_id: UUID, request: UpdateTaskRequest) -> TaskResponse:
            """Update an existing task."""
            try:
                command = UpdateTaskCommand(
                    task_id=task_id,
                    title=request.title,
                    description=request.description,
                    priority=request.priority,
                )
                task_dto = await self._task_management.update_task(command)
                return TaskResponse.from_dto(task_dto)
            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        @self._router.post("/tasks/{task_id}/assign", response_model=TaskResponse)
        async def assign_task(task_id: UUID, request: AssignTaskRequest) -> TaskResponse:
            """Assign a task to a user."""
            try:
                command = AssignTaskCommand(
                    task_id=task_id,
                    assignee_id=request.assignee_id,
                )
                task_dto = await self._task_management.assign_task(command)
                return TaskResponse.from_dto(task_dto)
            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        @self._router.post("/tasks/{task_id}/complete", response_model=TaskResponse)
        async def complete_task(task_id: UUID) -> TaskResponse:
            """Mark a task as completed."""
            try:
                task_dto = await self._task_management.complete_task(task_id)
                return TaskResponse.from_dto(task_dto)
            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        @self._router.get("/tasks", response_model=builtins.list[TaskResponse])
        async def get_tasks(
            status_filter: str | None = None,
            assignee_id: UUID | None = None,
            limit: int | None = None,
            offset: int = 0,
        ) -> builtins.list[TaskResponse]:
            """Get tasks with optional filters."""
            if status_filter:
                tasks = await self._task_management.get_tasks_by_status(status_filter)
            elif assignee_id:
                tasks = await self._task_management.get_tasks_by_assignee(assignee_id)
            else:
                tasks = await self._task_management.get_all_tasks(limit, offset)

            return [TaskResponse.from_dto(task) for task in tasks]

        @self._router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
        async def delete_task(task_id: UUID) -> None:
            """Delete a task."""
            deleted = await self._task_management.delete_task(task_id)
            if not deleted:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

        # User routes
        @self._router.post(
            "/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED
        )
        async def create_user(request: CreateUserRequest) -> UserResponse:
            """Create a new user."""
            try:
                command = CreateUserCommand(
                    first_name=request.first_name,
                    last_name=request.last_name,
                    email=request.email,
                    phone=request.phone,
                )
                user_dto = await self._user_management.create_user(command)
                return UserResponse.from_dto(user_dto)
            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        @self._router.get("/users/{user_id}", response_model=UserResponse)
        async def get_user(user_id: UUID) -> UserResponse:
            """Get a user by their ID."""
            user_dto = await self._user_management.get_user(user_id)
            if not user_dto:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            return UserResponse.from_dto(user_dto)

        @self._router.get("/users", response_model=builtins.list[UserResponse])
        async def get_users(
            limit: int | None = None,
            offset: int = 0,
        ) -> builtins.list[UserResponse]:
            """Get all users."""
            users = await self._user_management.get_all_users(limit, offset)
            return [UserResponse.from_dto(user) for user in users]

        @self._router.post("/users/{user_id}/activate", response_model=UserResponse)
        async def activate_user(user_id: UUID) -> UserResponse:
            """Activate a user."""
            try:
                user_dto = await self._user_management.activate_user(user_id)
                return UserResponse.from_dto(user_dto)
            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        @self._router.post("/users/{user_id}/deactivate", response_model=UserResponse)
        async def deactivate_user(user_id: UUID) -> UserResponse:
            """Deactivate a user."""
            try:
                user_dto = await self._user_management.deactivate_user(user_id)
                return UserResponse.from_dto(user_dto)
            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        @self._router.get("/users/{user_id}/workload", response_model=UserWorkloadResponse)
        async def get_user_workload(user_id: UUID) -> UserWorkloadResponse:
            """Get workload information for a user."""
            try:
                workload_dto = await self._user_management.get_user_workload(user_id)
                return UserWorkloadResponse.from_dto(workload_dto)
            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        @self._router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
        async def delete_user(user_id: UUID) -> None:
            """Delete a user."""
            deleted = await self._user_management.delete_user(user_id)
            if not deleted:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
