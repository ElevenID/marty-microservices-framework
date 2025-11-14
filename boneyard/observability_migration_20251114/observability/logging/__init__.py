"""
Unified logging framework for Marty Microservices Framework.

This module provides standardized logging with JSON format, correlation IDs,
trace ID support, and service context - ported from Marty's logging framework.
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime
from typing import Any

from opentelemetry import trace

# Default log format with service name and trace context
DEFAULT_LOG_FORMAT = (
    "%(asctime)s - %(levelname)s - [%(service_name)s] - [%(name)s] - "
    "[%(module)s.%(funcName)s:%(lineno)d] - %(message)s"
)

# Enhanced format with trace context
TRACE_LOG_FORMAT = (
    "%(asctime)s - %(levelname)s - [%(service_name)s] - [%(trace_id)s:%(span_id)s] - "
    "[%(name)s] - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s"
)

LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}

DEFAULT_LOG_LEVEL = "INFO"
LOG_OFF_LEVEL = "OFF"


class ServiceNameFilter(logging.Filter):
    """Filter to inject service name into log records."""

    def __init__(self, service_name: str) -> None:
        """Initialize filter with service name."""
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        """Add service name to log record."""
        record.service_name = self.service_name  # type: ignore[attr-defined]
        return True


class TraceContextFilter(logging.Filter):
    """Filter to inject trace context into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add trace_id and span_id to log record if available."""
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            span_context = current_span.get_span_context()
            record.trace_id = format(span_context.trace_id, "032x")  # type: ignore[attr-defined]
            record.span_id = format(span_context.span_id, "016x")  # type: ignore[attr-defined]
        else:
            record.trace_id = "00000000000000000000000000000000"  # type: ignore[attr-defined]
            record.span_id = "0000000000000000"  # type: ignore[attr-defined]
        return True


class CorrelationFilter(logging.Filter):
    """Filter to inject correlation ID into log records."""

    def __init__(self, correlation_id: str | None = None) -> None:
        """Initialize filter with correlation ID."""
        super().__init__()
        self.correlation_id = correlation_id or self._generate_correlation_id()

    def _generate_correlation_id(self) -> str:
        """Generate a new correlation ID."""
        return str(uuid.uuid4())

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation_id to log record."""
        record.correlation_id = self.correlation_id  # type: ignore[attr-defined]
        return True

    def update_correlation_id(self, correlation_id: str) -> None:
        """Update the correlation ID."""
        self.correlation_id = correlation_id


class UnifiedJSONFormatter(logging.Formatter):
    """JSON formatter for structured logging with comprehensive context."""

    def __init__(self, include_trace: bool = True, include_correlation: bool = True):
        super().__init__()
        self.include_trace = include_trace
        self.include_correlation = include_correlation

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with full context."""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service_name", "unknown"),
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "file": record.filename,
            "thread": record.thread,
            "process": record.process,
        }

        # Add trace context if available and enabled
        if self.include_trace:
            trace_id = getattr(record, "trace_id", None)
            span_id = getattr(record, "span_id", None)
            if trace_id and span_id:
                log_entry["trace_id"] = trace_id
                log_entry["span_id"] = span_id

        # Add correlation ID if available and enabled
        if self.include_correlation:
            correlation_id = getattr(record, "correlation_id", None)
            if correlation_id:
                log_entry["correlation_id"] = correlation_id

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info) if record.exc_info else None,
            }

        # Add extra fields from the record
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
                "exc_info",
                "exc_text",
                "stack_info",
                "service_name",
                "trace_id",
                "span_id",
                "correlation_id",
            }:
                log_entry[key] = value

        return json.dumps(log_entry, default=str, ensure_ascii=False)


class UnifiedServiceLogger:
    """
    Unified service logger with comprehensive context and structured logging.

    Combines Marty's logging patterns with MMF's audit capabilities.
    """

    def __init__(
        self,
        service_name: str,
        module_name: str | None = None,
        enable_json_logging: bool = True,
        enable_trace_context: bool = True,
        enable_correlation: bool = True,
        correlation_id: str | None = None,
        log_level: str = DEFAULT_LOG_LEVEL,
    ) -> None:
        """
        Initialize unified service logger.

        Args:
            service_name: Name of the service for context
            module_name: Module name (typically __name__)
            enable_json_logging: Whether to use JSON format
            enable_trace_context: Whether to include trace context
            enable_correlation: Whether to include correlation IDs
            correlation_id: Specific correlation ID to use
            log_level: Logging level
        """
        self.service_name = service_name
        self.module_name = module_name or service_name
        self.enable_json_logging = enable_json_logging
        self.enable_trace_context = enable_trace_context
        self.enable_correlation = enable_correlation

        # Create the underlying logger
        self._logger = logging.getLogger(self.module_name)
        self._setup_logger(log_level, correlation_id)

        # Add service context to all log messages
        self._service_context = {"service": service_name}

    def _setup_logger(self, log_level: str, correlation_id: str | None) -> None:
        """Set up the logger with appropriate handlers and filters."""
        # Clear existing handlers
        self._logger.handlers.clear()

        # Set log level
        if log_level != LOG_OFF_LEVEL:
            self._logger.setLevel(LOG_LEVELS.get(log_level, logging.INFO))
        else:
            self._logger.setLevel(logging.CRITICAL + 1)  # Effectively turn off logging

        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)

        # Choose formatter
        if self.enable_json_logging:
            formatter = UnifiedJSONFormatter(
                include_trace=self.enable_trace_context, include_correlation=self.enable_correlation
            )
        else:
            format_string = TRACE_LOG_FORMAT if self.enable_trace_context else DEFAULT_LOG_FORMAT
            formatter = logging.Formatter(format_string)

        console_handler.setFormatter(formatter)

        # Add filters
        console_handler.addFilter(ServiceNameFilter(self.service_name))

        if self.enable_trace_context:
            console_handler.addFilter(TraceContextFilter())

        if self.enable_correlation:
            self.correlation_filter = CorrelationFilter(correlation_id)
            console_handler.addFilter(self.correlation_filter)

        self._logger.addHandler(console_handler)

    def update_correlation_id(self, correlation_id: str) -> None:
        """Update the correlation ID for this logger."""
        if self.enable_correlation and hasattr(self, "correlation_filter"):
            self.correlation_filter.update_correlation_id(correlation_id)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log debug message with service context."""
        self._log_with_context(logging.DEBUG, msg, args, kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log info message with service context."""
        self._log_with_context(logging.INFO, msg, args, kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log warning message with service context."""
        self._log_with_context(logging.WARNING, msg, args, kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log error message with service context."""
        self._log_with_context(logging.ERROR, msg, args, kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log critical message with service context."""
        self._log_with_context(logging.CRITICAL, msg, args, kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log exception with service context and stack trace."""
        kwargs.setdefault("exc_info", True)
        self.error(msg, *args, **kwargs)

    def _log_with_context(
        self, level: int, msg: str, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> None:
        """Log message with service context."""
        # Add service context to extra fields
        extra = kwargs.setdefault("extra", {})
        extra.update(self._service_context)

        self._logger.log(level, msg, *args, **kwargs)

    # Service lifecycle logging methods (ported from Marty)
    def log_service_startup(self, additional_info: dict[str, Any] | None = None) -> None:
        """Log standardized service startup message."""
        info = {"status": "starting", **self._service_context}
        if additional_info:
            info.update(additional_info)

        self.info("Service starting up", extra=info)

    def log_service_ready(
        self,
        port: int | None = None,
        additional_info: dict[str, Any] | None = None,
    ) -> None:
        """Log standardized service ready message."""
        info = {"status": "ready", **self._service_context}
        if port:
            info["port"] = port
        if additional_info:
            info.update(additional_info)

        self.info("Service ready", extra=info)

    def log_service_shutdown(self, reason: str | None = None) -> None:
        """Log standardized service shutdown message."""
        info = {"status": "shutting_down", **self._service_context}
        if reason:
            info["reason"] = reason

        self.info("Service shutting down", extra=info)

    def log_request_start(self, request_id: str, operation: str, **context: Any) -> None:
        """Log start of request processing."""
        info = {
            "request_id": request_id,
            "operation": operation,
            "phase": "start",
            **self._service_context,
            **context,
        }
        self.info("Request started", extra=info)

    def log_request_end(
        self, request_id: str, operation: str, duration: float, success: bool = True, **context: Any
    ) -> None:
        """Log end of request processing."""
        info = {
            "request_id": request_id,
            "operation": operation,
            "phase": "end",
            "duration": duration,
            "success": success,
            **self._service_context,
            **context,
        }
        if success:
            self.info("Request completed", extra=info)
        else:
            self.error("Request failed", extra=info)

    def log_performance_metric(
        self, metric_name: str, value: float, unit: str = "ms", **context: Any
    ) -> None:
        """Log performance metric."""
        info = {
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            "metric_type": "performance",
            **self._service_context,
            **context,
        }
        self.info("Performance metric", extra=info)

    def log_business_event(self, event_type: str, **context: Any) -> None:
        """Log business event."""
        info = {
            "event_type": event_type,
            "event_category": "business",
            **self._service_context,
            **context,
        }
        self.info("Business event", extra=info)

    def log_security_event(self, event_type: str, severity: str = "info", **context: Any) -> None:
        """Log security event."""
        info = {
            "event_type": event_type,
            "event_category": "security",
            "severity": severity,
            **self._service_context,
            **context,
        }

        # Use appropriate log level based on severity
        if severity == "critical":
            self.critical("Security event", extra=info)
        elif severity == "error":
            self.error("Security event", extra=info)
        elif severity == "warning":
            self.warning("Security event", extra=info)
        else:
            self.info("Security event", extra=info)


def get_unified_logger(
    service_name: str, module_name: str | None = None, **kwargs: Any
) -> UnifiedServiceLogger:
    """
    Get a unified service logger instance.

    This is the main entry point for getting a standardized logger
    that works across all MMF services.
    """
    return UnifiedServiceLogger(service_name, module_name, **kwargs)


def setup_unified_logging(
    service_name: str,
    log_level: str = DEFAULT_LOG_LEVEL,
    enable_json: bool = True,
    enable_trace: bool = True,
    enable_correlation: bool = True,
) -> UnifiedServiceLogger:
    """
    Set up unified logging for a service.

    This function should be called early in service startup to establish
    consistent logging across the service.
    """
    # Optionally configure based on environment variables
    log_level = os.getenv("LOG_LEVEL", log_level)
    enable_json = os.getenv("LOG_FORMAT", "json" if enable_json else "text") == "json"
    enable_trace = os.getenv("ENABLE_TRACE_LOGGING", str(enable_trace)).lower() == "true"
    enable_correlation = (
        os.getenv("ENABLE_CORRELATION_LOGGING", str(enable_correlation)).lower() == "true"
    )

    return UnifiedServiceLogger(
        service_name=service_name,
        log_level=log_level,
        enable_json_logging=enable_json,
        enable_trace_context=enable_trace,
        enable_correlation=enable_correlation,
    )
