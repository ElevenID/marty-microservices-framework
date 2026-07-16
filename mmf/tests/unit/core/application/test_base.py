from dataclasses import dataclass
from datetime import datetime
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from mmf.core.application.base import (
    BusinessRuleError,
    Command,
    CommandError,
    CommandRequest,
    CommandResult,
    CommandStatus,
    ConflictError,
    NotFoundError,
    Query,
    QueryError,
    QueryRequest,
    QueryResult,
    UnauthorizedError,
    UseCase,
    ValidationError,
    WriteCommand,
    WriteError,
    create_simple_query,
    create_simple_write_command,
)


@dataclass
class MockRequest(CommandRequest):
    data: str = "test"


@dataclass
class MockQueryRequest(QueryRequest):
    filter_value: str = "test"


class TestCommandResult:
    def test_is_success(self):
        result = CommandResult(request_id="123", status=CommandStatus.COMPLETED, data="success")
        assert result.is_success is True
        assert result.is_failure is False

    def test_is_failure_status(self):
        result = CommandResult(request_id="123", status=CommandStatus.FAILED, error_message="error")
        assert result.is_success is False
        assert result.is_failure is True

    def test_is_failure_error_message(self):
        result = CommandResult(
            request_id="123", status=CommandStatus.COMPLETED, error_message="error"
        )
        assert result.is_success is False
        assert result.is_failure is True


class TestCommandRequest:
    def test_defaults(self):
        req = CommandRequest()
        assert req.request_id is not None
        assert req.correlation_id is not None
        assert isinstance(req.timestamp, datetime)
        assert req.metadata == {}

    def test_custom_values(self):
        req = CommandRequest(
            request_id="req-1",
            correlation_id="corr-1",
            user_id="user-1",
            tenant_id="tenant-1",
            metadata={"key": "value"},
        )
        assert req.request_id == "req-1"
        assert req.correlation_id == "corr-1"
        assert req.user_id == "user-1"
        assert req.tenant_id == "tenant-1"
        assert req.metadata == {"key": "value"}


class TestQueryRequest:
    def test_defaults(self):
        req = QueryRequest()
        assert req.page == 1
        assert req.page_size == 20
        assert req.sort_order == "asc"
        assert req.filters == {}

    def test_custom_values(self):
        req = QueryRequest(
            page=2, page_size=50, sort_by="name", sort_order="desc", filters={"active": True}
        )
        assert req.page == 2
        assert req.page_size == 50
        assert req.sort_by == "name"
        assert req.sort_order == "desc"
        assert req.filters == {"active": True}


class TestCommandExecution:
    class SuccessCommand(Command[MockRequest, str]):
        async def execute(self, request: MockRequest) -> str:
            return f"Processed {request.data}"

    class FailingCommand(Command[MockRequest, str]):
        async def execute(self, request: MockRequest) -> str:
            raise ValueError("Something went wrong")

    @pytest.mark.asyncio
    async def test_execute_with_result_success(self):
        cmd = self.SuccessCommand()
        req = MockRequest(data="input")

        result = await cmd.execute_with_result(req)

        assert result.status == CommandStatus.COMPLETED
        assert result.data == "Processed input"
        assert result.error_message is None
        assert result.execution_time_ms is not None
        assert result.request_id == req.request_id

    @pytest.mark.asyncio
    async def test_execute_with_result_failure(self):
        cmd = self.FailingCommand()
        req = MockRequest(data="input")

        result = await cmd.execute_with_result(req)

        assert result.status == CommandStatus.FAILED
        assert result.data is None
        assert result.error_message == "Something went wrong"
        assert result.execution_time_ms is not None
        assert result.request_id == req.request_id


class TestQueryExecution:
    class SuccessQuery(Query[MockQueryRequest, list[str]]):
        async def execute(self, request: MockQueryRequest) -> list[str]:
            return ["item1", "item2"]

    class FailingQuery(Query[MockQueryRequest, list[str]]):
        async def execute(self, request: MockQueryRequest) -> list[str]:
            raise ValueError("Query failed")

    @pytest.mark.asyncio
    async def test_execute_paginated_success(self):
        query = self.SuccessQuery()
        req = MockQueryRequest(page=2, page_size=10)

        result = await query.execute_paginated(req)

        assert isinstance(result, QueryResult)
        assert result.data == ["item1", "item2"]
        assert result.page == 2
        assert result.page_size == 10
        assert result.execution_time_ms is not None
        assert result.request_id == req.request_id

    @pytest.mark.asyncio
    async def test_execute_paginated_failure(self):
        query = self.FailingQuery()
        req = MockQueryRequest()

        with pytest.raises(QueryError) as exc_info:
            await query.execute_paginated(req)

        assert "Query execution failed: Query failed" in str(exc_info.value)


class TestWriteCommandExecution:
    class SimpleWrite(WriteCommand[MockRequest, str]):
        async def execute(self, request: MockRequest) -> str:
            return "written"

    @pytest.mark.asyncio
    async def test_execute_with_events(self):
        cmd = self.SimpleWrite()
        req = MockRequest()

        result = await cmd.execute_with_events(req)

        assert result.status == CommandStatus.COMPLETED
        assert result.data == "written"
        # Currently execute_with_events just calls execute_with_result
        # but we verify it works as expected


class TestFactories:
    @pytest.mark.asyncio
    async def test_create_simple_query(self):
        async def my_func(req):
            return f"query: {req}"

        QueryClass = create_simple_query(my_func)
        query = QueryClass()

        result = await query.execute("test")
        assert result == "query: test"

    @pytest.mark.asyncio
    async def test_create_simple_write_command(self):
        async def my_func(req):
            return f"write: {req}"

        WriteClass = create_simple_write_command(my_func)
        cmd = WriteClass()

        result = await cmd.execute("test")
        assert result == "write: test"


class TestExceptions:
    def test_exceptions_inheritance(self):
        assert issubclass(ValidationError, CommandError)
        assert issubclass(BusinessRuleError, CommandError)
        assert issubclass(NotFoundError, CommandError)
        assert issubclass(UnauthorizedError, CommandError)
        assert issubclass(ConflictError, CommandError)
        assert issubclass(QueryError, CommandError)
        assert issubclass(WriteError, CommandError)

    def test_exception_messages(self):
        err = CommandError("base error")
        assert str(err) == "base error"

        err = ValidationError("invalid input")
        assert str(err) == "invalid input"


class TestUseCase:
    class ConcreteUseCase(UseCase[str, str]):
        async def execute(self, request: str) -> str:
            return f"processed {request}"

    @pytest.mark.asyncio
    async def test_use_case_execution(self):
        use_case = self.ConcreteUseCase()
        result = await use_case.execute("test")
        assert result == "processed test"


class TestCommandStatus:
    def test_values(self):
        assert CommandStatus.PENDING.value == "pending"
        assert CommandStatus.EXECUTING.value == "executing"
        assert CommandStatus.COMPLETED.value == "completed"
        assert CommandStatus.FAILED.value == "failed"
