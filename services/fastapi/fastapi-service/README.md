# {{project_name}}

{{project_description}}

## Features

- FastAPI web framework with async support
- Structured logging with JSON output
- Prometheus metrics collection
- Health and readiness checks
- Automatic API documentation
- CORS and compression middleware
- Docker and Kubernetes ready
- Comprehensive error handling

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
python main.py

# Or with uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port {{service_port}}
```

### API Documentation

Once running, visit:

- API docs: <http://localhost:{{service_port}}/docs>
- ReDoc: <http://localhost:{{service_port}}/redoc>

### Health Checks

- Health: <http://localhost:{{service_port}}/health>
- Readiness: <http://localhost:{{service_port}}/ready>

### Metrics

- Prometheus metrics: <http://localhost:{{service_port}}/metrics>

## Configuration

Set environment variables:

```bash
HOST=0.0.0.0
PORT={{service_port}}
DEBUG=false
```

## Docker

```bash
# Build image
docker build -t {{project_slug}} .

# Run container
docker run -p {{service_port}}:{{service_port}} {{project_slug}}
```

## Kubernetes

```bash
# Deploy to Kubernetes
kubectl apply -f k8s/
```

## Development

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=main
```

### Code Quality

```bash
# Format code
black main.py

# Sort imports
isort main.py

# Lint code
flake8 main.py
```

## Project Structure

```
{{project_slug}}/
├── main.py              # Main application
├── requirements.txt     # Dependencies
├── Dockerfile          # Docker configuration
├── k8s/                # Kubernetes manifests
├── tests/              # Test files
└── README.md           # This file
```

## API Reference

### Root Endpoint

```http
GET /
```

Returns service information.

### Status Endpoint

```http
GET /api/status
```

Returns current service status.

## License

{{license}}
