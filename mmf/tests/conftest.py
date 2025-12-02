import sys
from unittest.mock import MagicMock

# Mock redis module to avoid installation requirement for unit tests
redis_mock = MagicMock()
redis_exceptions_mock = MagicMock()
redis_asyncio_mock = MagicMock()

sys.modules["redis"] = redis_mock
sys.modules["redis.exceptions"] = redis_exceptions_mock
sys.modules["redis.asyncio"] = redis_asyncio_mock

# Also mock RedisError
redis_exceptions_mock.RedisError = Exception
