FROM python:3.13-slim

WORKDIR /app

# Install system dependencies and uv
RUN apt-get update && apt-get install -y     curl     && rm -rf /var/lib/apt/lists/*     && curl -LsSf https://astral.sh/uv/install.sh | sh     && mv /root/.local/bin/uv /usr/local/bin/uv

# Install dependencies
RUN uv pip install --system     fastapi>=0.104.0     uvicorn[standard]>=0.24.0     pydantic>=2.5.0     redis>=5.0.0     structlog>=23.2.0     pydantic-settings>=2.1.0     tenacity>=8.2.0     httpx>=0.25.0     sqlalchemy>=2.0.0     sqlmodel>=0.0.14     python-multipart>=0.0.6     click>=8.1.0     rich>=13.0.0     jinja2>=3.1.0     pyyaml>=6.0.0     aiohttp>=3.9.0     aiofiles>=23.2.0     aiosqlite>=0.19.0     psutil>=5.9.0     jsonschema>=4.20.0     dishka>=1.0.0     taskiq>=0.11.0     taskiq-fastapi>=0.3.0     prometheus-fastapi-instrumentator>=6.0.0

# Copy framework
COPY mmf/ /app/mmf/

# Copy service code
COPY examples/petstore_domain/services/pet_service/ /app/examples/petstore_domain/services/pet_service/

# Set Python path
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "examples.petstore_domain.services.pet_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
