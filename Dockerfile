FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies and uv
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv \
    && mv /root/.local/bin/uvx /usr/local/bin/uvx

# Install dependencies for the identity service
RUN uv pip install --system \
    fastapi>=0.104.0 \
    uvicorn[standard]>=0.24.0 \
    pydantic>=2.5.0 \
    pyjwt>=2.10.1 \
    sqlalchemy>=2.0.0 \
    asyncpg>=0.29.0 \
    pydantic-settings>=2.11.0 \
    aiofiles>=24.1.0 \
    click>=8.1.0 \
    pyyaml>=6.0.0 \
    hvac>=2.3.0 \
    redis>=5.0.0 \
    bcrypt>=4.0.1

# Copy application code
COPY mmf/ ./mmf/
COPY platform_plugins/ ./platform_plugins/

# Set Python path
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application using system Python
CMD ["python", "-m", "uvicorn", "mmf.services.identity.infrastructure.adapters.http_adapter:app", "--host", "0.0.0.0", "--port", "8000"]
