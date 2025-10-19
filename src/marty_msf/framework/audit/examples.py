"""
Comprehensive examples for the Enterprise Audit Logging Framework.

This module demonstrates various usage patterns and best practices
for implementing audit logging in microservices.
"""

import asyncio
import builtins
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPBearer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from marty_msf.framework.audit import (
    AuditConfig,
    AuditContext,
    AuditEventType,
    AuditMiddlewareConfig,
    AuditOutcome,
    AuditSeverity,
    audit_context,
    setup_fastapi_audit_middleware,
)

# FastAPI example
try:

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

# Database example
try:

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False


# Framework imports

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Example 1: Basic Audit Logging Setup
async def basic_audit_example():
    """Demonstrate basic audit logging setup and usage."""

    print("\n=== Basic Audit Logging Example ===")

    # Configure audit logging
    config = AuditConfig()
    config.enable_file_logging = True
    config.enable_console_logging = True
    config.enable_database_logging = False  # Disable for this example
    config.log_file_path = Path("examples/audit_basic.log")

    # Create audit context
    context = AuditContext(
        service_name="example-service",
        service_version="1.0.0",
        environment="development",
        node_id="node-001",
    )

    # Use audit logging
    async with audit_context(config, context) as audit_logger:
        # Log authentication events
        await audit_logger.log_auth_event(
            AuditEventType.USER_LOGIN,
            user_id="user123",
            source_ip="192.168.1.100",
            details={"login_method": "password", "user_agent": "Mozilla/5.0"},
        )

        # Log API events
        await audit_logger.log_api_event(
            method="GET",
            endpoint="/api/users/123",
            status_code=200,
            user_id="user123",
            source_ip="192.168.1.100",
            duration_ms=45.2,
            response_size=1024,
        )

        # Log data events
        await audit_logger.log_data_event(
            AuditEventType.DATA_ACCESS,
            resource_type="user",
            resource_id="123",
            action="read",
            user_id="user123",
            changes={"fields_accessed": ["name", "email"]},
        )

        # Log security events
        await audit_logger.log_security_event(
            AuditEventType.SECURITY_VIOLATION,
            "Multiple failed login attempts detected",
            severity=AuditSeverity.HIGH,
            source_ip="192.168.1.200",
            details={"attempts": 5, "timeframe": "5 minutes"},
        )

        # Log system events
        await audit_logger.log_system_event(
            AuditEventType.SYSTEM_STARTUP,
            "Service started successfully",
            details={"startup_time": "2.3s", "modules_loaded": 15},
        )

    print("Basic audit logging example completed. Check examples/audit_basic.log")


# Example 2: Custom Event Builder Usage
async def custom_event_example():
    """Demonstrate custom audit event building."""

    print("\n=== Custom Event Builder Example ===")

    config = AuditConfig()
    config.enable_console_logging = True
    config.enable_file_logging = False

    context = AuditContext(
        service_name="custom-service", service_version="2.0.0", environment="production"
    )

    async with audit_context(config, context) as audit_logger:
        # Build complex custom event
        builder = audit_logger.create_event_builder()

        event = (
            builder.event_type(AuditEventType.BUSINESS_LOGIC)
            .message("User completed complex business transaction")
            .user("user456")
            .action("complete_transaction")
            .severity(AuditSeverity.MEDIUM)
            .outcome(AuditOutcome.SUCCESS)
            .resource("transaction", "txn-789")
            .request(source_ip="10.0.0.50", method="POST", endpoint="/api/transactions")
            .performance(duration_ms=1250.0, data_size=2048)
            .detail("transaction_amount", 1500.00)
            .detail("currency", "USD")
            .detail("merchant_id", "merchant-123")
            .detail("payment_method", "credit_card")
            .detail("steps_completed", ["validation", "authorization", "settlement"])
            .build()
        )

        await audit_logger.log_event(event)

        # Build error event with encryption
        error_event = (
            builder.event_type(AuditEventType.DATA_PROCESSING)
            .message("Sensitive data processing failed")
            .severity(AuditSeverity.HIGH)
            .outcome(AuditOutcome.ERROR)
            .action("process_sensitive_data")
            .error(
                "Data validation failed",
                "ValidationError",
                {"field": "ssn", "reason": "invalid_format"},
            )
            .sensitive_detail("customer_ssn", "123-45-6789")  # Will be encrypted
            .sensitive_detail("customer_dob", "1990-01-01")  # Will be encrypted
            .build()
        )

        await audit_logger.log_event(error_event)

    print("Custom event builder example completed")


# Example 3: FastAPI Integration
if FASTAPI_AVAILABLE:

    def create_fastapi_example():
        """Create FastAPI application with audit logging."""

        print("\n=== FastAPI Integration Example ===")

        app = FastAPI(title="Audit Example API")

        # Configure audit middleware
        middleware_config = AuditMiddlewareConfig()
        middleware_config.log_requests = True
        middleware_config.log_responses = True
        middleware_config.log_headers = True
        middleware_config.log_body = True
        middleware_config.exclude_paths = ["/health", "/metrics"]
        middleware_config.slow_request_threshold_ms = 500.0
        middleware_config.detect_anomalies = True

        # Setup audit middleware
        setup_fastapi_audit_middleware(app, middleware_config)

        # Security dependency
        security = HTTPBearer()

        async def get_current_user(token: str = Depends(security)):
            # Simulate user extraction from token
            return {"user_id": "user123", "username": "john_doe"}

        @app.on_event("startup")
        async def startup():
            # Initialize audit logging
            config = AuditConfig()
            config.enable_file_logging = True
            config.enable_console_logging = True
            config.log_file_path = Path("examples/audit_fastapi.log")

            AuditContext(
                service_name="fastapi-example",
                service_version="1.0.0",
                environment="development",
            )

            # This would typically be managed by a dependency injection container
            # For this example, we'll simulate it
            print("FastAPI audit logging initialized")

        @app.get("/health")
        async def health_check():
            return {"status": "healthy"}

        @app.get("/api/users/{user_id}")
        async def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
            # Simulate user retrieval
            if user_id == "999":
                raise HTTPException(status_code=404, detail="User not found")

            return {
                "id": user_id,
                "name": f"User {user_id}",
                "email": f"user{user_id}@example.com",
            }

        @app.post("/api/users")
        async def create_user(
            user_data: builtins.dict[str, Any],
            current_user: dict = Depends(get_current_user),
        ):
            # Simulate user creation
            user_id = "new_user_123"

            # Manual audit logging for business events
            audit_logger = audit_context.get_audit_logger()
            if audit_logger:
                await audit_logger.log_data_event(
                    AuditEventType.DATA_CREATE,
                    resource_type="user",
                    resource_id=user_id,
                    action="create",
                    user_id=current_user["user_id"],
                    changes=user_data,
                )

            return {"id": user_id, "status": "created"}

        @app.put("/api/users/{user_id}")
        async def update_user(
            user_id: str,
            user_data: builtins.dict[str, Any],
            current_user: dict = Depends(get_current_user),
        ):
            # Simulate user update
            audit_logger = audit_context.get_audit_logger()
            if audit_logger:
                await audit_logger.log_data_event(
                    AuditEventType.DATA_UPDATE,
                    resource_type="user",
                    resource_id=user_id,
                    action="update",
                    user_id=current_user["user_id"],
                    changes=user_data,
                )

            return {"id": user_id, "status": "updated"}

        @app.delete("/api/users/{user_id}")
        async def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
            # Simulate user deletion
            audit_logger = audit_context.get_audit_logger()
            if audit_logger:
                await audit_logger.log_data_event(
                    AuditEventType.DATA_DELETE,
                    resource_type="user",
                    resource_id=user_id,
                    action="delete",
                    user_id=current_user["user_id"],
                )

            return {"id": user_id, "status": "deleted"}

        print("FastAPI example application created")
        print("Run with: uvicorn examples:app --reload")
        return app

    # Create the app
    app = create_fastapi_example()


# Example 4: Database Integration
if SQLALCHEMY_AVAILABLE:

    async def database_integration_example():
        """Demonstrate database audit logging integration."""

        print("\n=== Database Integration Example ===")

        # Create in-memory SQLite database for example
        engine = create_engine("sqlite:///examples/audit_example.db", echo=False)
        SessionLocal = sessionmaker(bind=engine)

        # Create session
        db_session = SessionLocal()

        try:
            # Configure audit logging with database destination
            config = AuditConfig()
            config.enable_database_logging = True
            config.enable_console_logging = True
            config.enable_file_logging = False
            config.batch_size = 5  # Small batch for demonstration
            config.encrypt_sensitive_data = True

            context = AuditContext(
                service_name="database-example",
                service_version="1.0.0",
                environment="development",
            )

            async with audit_context(config, context, db_session) as audit_logger:
                # Log various events
                for i in range(10):
                    await audit_logger.log_api_event(
                        method="GET",
                        endpoint=f"/api/items/{i}",
                        status_code=200,
                        user_id=f"user{i % 3}",
                        source_ip=f"192.168.1.{100 + i}",
                        duration_ms=50.0 + i * 10,
                    )

                    # Add some variety
                    if i % 3 == 0:
                        await audit_logger.log_security_event(
                            AuditEventType.AUTH_SUCCESS,
                            "User authentication successful",
                            source_ip=f"192.168.1.{100 + i}",
                            user_id=f"user{i % 3}",
                        )

                # Wait for batch processing
                await asyncio.sleep(1)

                # Search for events
                print("\nSearching for events...")
                search_count = 0
                async for event in audit_logger.search_events(
                    event_type=AuditEventType.API_REQUEST, limit=5
                ):
                    print(f"Found event: {event.action} at {event.timestamp}")
                    search_count += 1

                print(f"Found {search_count} events in search")

                # Get statistics
                stats = await audit_logger.get_audit_statistics()
                print("\nAudit Statistics:")
                print(f"Total events: {stats['total_events']}")
                print(f"Event types: {stats['event_counts']}")
                print(f"Security events: {stats['security_events']}")

        finally:
            db_session.close()

        print("Database integration example completed")


# Example 5: Performance and Load Testing
async def performance_example():
    """Demonstrate audit logging performance with high load."""

    print("\n=== Performance Example ===")

    config = AuditConfig()
    config.enable_file_logging = True
    config.enable_console_logging = False  # Disable for performance
    config.async_logging = True
    config.flush_interval_seconds = 5
    config.log_file_path = Path("examples/audit_performance.log")

    context = AuditContext(
        service_name="performance-test",
        service_version="1.0.0",
        environment="load-test",
    )

    async with audit_context(config, context) as audit_logger:
        # Simulate high-volume logging
        start_time = datetime.now()
        event_count = 1000

        print(f"Logging {event_count} events...")

        tasks = []
        for i in range(event_count):
            task = audit_logger.log_api_event(
                method="GET",
                endpoint=f"/api/load-test/{i}",
                status_code=200 if i % 10 != 0 else 500,
                user_id=f"user{i % 100}",
                source_ip=f"10.0.{i // 256}.{i % 256}",
                duration_ms=float(i % 100),
            )
            tasks.append(task)

            # Batch the tasks to avoid overwhelming the system
            if len(tasks) >= 100:
                await asyncio.gather(*tasks)
                tasks = []

        # Process remaining tasks
        if tasks:
            await asyncio.gather(*tasks)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print(f"Logged {event_count} events in {duration:.2f} seconds")
        print(f"Rate: {event_count / duration:.2f} events/second")

        # Allow time for async processing
        await asyncio.sleep(2)

    print("Performance example completed")


# Example 6: Compliance and Retention
async def compliance_example():
    """Demonstrate compliance features and data retention."""

    print("\n=== Compliance Example ===")

    config = AuditConfig()
    config.enable_file_logging = True
    config.enable_console_logging = True
    config.encrypt_sensitive_data = True
    config.compliance_mode = True
    config.immutable_logging = True
    config.retention_days = 30
    config.log_file_path = Path("examples/audit_compliance.log")

    context = AuditContext(
        service_name="compliance-service",
        service_version="1.0.0",
        environment="production",
        compliance_requirements=["SOX", "GDPR", "HIPAA"],
    )

    async with audit_context(config, context) as audit_logger:
        # Log compliance-sensitive events
        await audit_logger.log_data_event(
            AuditEventType.DATA_ACCESS,
            resource_type="patient_record",
            resource_id="patient-12345",
            action="view",
            user_id="doctor-001",
            changes={"fields_accessed": ["name", "diagnosis", "treatment"]},
        )

        # Log with sensitive data encryption
        builder = audit_logger.create_event_builder()
        event = (
            builder.event_type(AuditEventType.DATA_EXPORT)
            .message("Patient data exported for research")
            .user("researcher-005")
            .action("export_patient_data")
            .severity(AuditSeverity.HIGH)
            .outcome(AuditOutcome.SUCCESS)
            .resource("patient_data", "export-789")
            .sensitive_detail("patient_ssn", "123-45-6789")
            .sensitive_detail("patient_dob", "1980-05-15")
            .detail("research_protocol", "PROTO-2024-001")
            .detail("export_format", "anonymized_csv")
            .build()
        )

        await audit_logger.log_event(event)

        # Log regulatory compliance event
        await audit_logger.log_system_event(
            AuditEventType.COMPLIANCE_CHECK,
            "GDPR data retention check completed",
            details={
                "records_reviewed": 10000,
                "records_expired": 50,
                "records_purged": 45,
                "compliance_status": "PASSED",
            },
        )

    print("Compliance example completed")


# Main example runner
async def run_all_examples():
    """Run all audit logging examples."""

    print("Starting Enterprise Audit Logging Framework Examples")
    print("=" * 60)

    # Create examples directory
    Path("examples").mkdir(exist_ok=True)

    try:
        # Run basic examples
        await basic_audit_example()
        await custom_event_example()

        # Run database example if available
        if SQLALCHEMY_AVAILABLE:
            await database_integration_example()
        else:
            print("\nSQLAlchemy not available, skipping database example")

        # Run performance and compliance examples
        await performance_example()
        await compliance_example()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("\nCheck the 'examples/' directory for generated audit log files:")
        print("- audit_basic.log - Basic audit logging")
        print("- audit_fastapi.log - FastAPI integration")
        print("- audit_example.db - Database audit logs")
        print("- audit_performance.log - Performance test logs")
        print("- audit_compliance.log - Compliance example logs")

        if FASTAPI_AVAILABLE:
            print("\nTo test FastAPI integration:")
            print("1. pip install 'fastapi[all]'")
            print("2. uvicorn framework.audit.examples:app --reload")
            print("3. Visit http://localhost:8000/docs")

    except Exception as e:
        print(f"Error running examples: {e}")
        logger.exception("Example execution failed")


if __name__ == "__main__":
    # Run examples
    asyncio.run(run_all_examples())
