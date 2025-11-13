"""
Configuration example for the Morty service.

This demonstrates how to configure the service for different environments.
"""

# Development configuration
development_config = {
    "service": {
        "name": "morty-service",
        "version": "1.0.0",
        "host": "0.0.0.0",
        "port": 8080,
    },
    "database": {
        "url": "postgresql+asyncpg://morty:password@localhost/morty_dev",
        "debug": True,
    },
    "redis": {
        "url": "redis://localhost:6379/0",
    },
    "kafka": {
        "bootstrap_servers": ["localhost:9092"],
        "client_id": "morty-service",
    },
    "email": {
        "from_email": "morty@company.com",
        "smtp_host": "smtp.company.com",
        "smtp_port": 587,
    },
    "observability": {
        "log_level": "DEBUG",
        "log_format": "json",
        "metrics_enabled": True,
    },
}

# Production configuration
production_config = {
    "service": {
        "name": "morty-service",
        "version": "1.0.0",
        "host": "0.0.0.0",
        "port": 8080,
    },
    "database": {
        "url": "postgresql+asyncpg://morty:${DB_PASSWORD}@db-cluster:5432/morty_prod",
        "debug": False,
        "pool_size": 20,
        "max_overflow": 30,
    },
    "redis": {
        "url": "redis://redis-cluster:6379/0",
        "pool_size": 10,
    },
    "kafka": {
        "bootstrap_servers": ["kafka-1:9092", "kafka-2:9092", "kafka-3:9092"],
        "client_id": "morty-service",
        "security_protocol": "SASL_SSL",
    },
    "email": {
        "from_email": "morty@company.com",
        "smtp_host": "smtp.company.com",
        "smtp_port": 587,
        "use_tls": True,
    },
    "observability": {
        "log_level": "INFO",
        "log_format": "json",
        "metrics_enabled": True,
        "tracing_enabled": True,
    },
}

# Testing configuration
testing_config = {
    "service": {
        "name": "morty-service-test",
        "version": "1.0.0",
        "host": "0.0.0.0",
        "port": 8080,
    },
    "database": {
        "url": "postgresql+asyncpg://morty:password@localhost/morty_test",
        "debug": True,
    },
    "redis": {
        "url": None,  # Use in-memory cache for testing
    },
    "kafka": {
        "bootstrap_servers": None,  # Use mock event publisher for testing
    },
    "email": {
        "from_email": "test@company.com",
        "smtp_host": None,  # Use mock email service for testing
    },
    "observability": {
        "log_level": "DEBUG",
        "log_format": "text",
        "metrics_enabled": False,
    },
}
