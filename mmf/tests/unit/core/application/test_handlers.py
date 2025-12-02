import pytest

from mmf.core.application.base import Command, CommandResult, Query, QueryResult
from mmf.core.application.handlers import (
    CommandHandler,
    QueryHandler,
    command_handler,
    query_handler,
)


class TestHandlers:
    def test_command_handler_decorator(self):
        @command_handler("test_command")
        class MyCommandHandler(CommandHandler):
            async def handle(self, command: Command) -> CommandResult:
                return CommandResult.success()

            def can_handle(self, command: Command) -> bool:
                return True

        assert MyCommandHandler._command_type == "test_command"

    def test_query_handler_decorator(self):
        @query_handler("test_query")
        class MyQueryHandler(QueryHandler):
            async def handle(self, query: Query) -> QueryResult:
                return QueryResult.success("result")

            def can_handle(self, query: Query) -> bool:
                return True

        assert MyQueryHandler._query_type == "test_query"

    @pytest.mark.asyncio
    async def test_command_handler_implementation(self):
        class MyCommand(Command):
            async def execute(self, request):
                return "executed"

        class MyCommandHandler(CommandHandler[MyCommand]):
            async def handle(self, command: MyCommand) -> CommandResult:
                from mmf.core.application.base import CommandStatus

                return CommandResult(
                    request_id="test-id", status=CommandStatus.COMPLETED, data="handled"
                )

            def can_handle(self, command: Command) -> bool:
                return isinstance(command, MyCommand)

        handler = MyCommandHandler()
        command = MyCommand()

        assert handler.can_handle(command)
        result = await handler.handle(command)
        assert result.is_success
        assert result.data == "handled"

    @pytest.mark.asyncio
    async def test_query_handler_implementation(self):
        class MyQuery(Query):
            async def execute(self, request):
                return "query_executed"

        class MyQueryHandler(QueryHandler[MyQuery, str]):
            async def handle(self, query: MyQuery) -> QueryResult[str]:
                return QueryResult(request_id="test-id", data="query_result")

            def can_handle(self, query: Query) -> bool:
                return isinstance(query, MyQuery)

        handler = MyQueryHandler()
        query = MyQuery()

        assert handler.can_handle(query)
        result = await handler.handle(query)
        assert result.data == "query_result"
