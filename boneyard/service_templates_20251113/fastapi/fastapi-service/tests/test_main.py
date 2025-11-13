"""
Test suite for {{project_name}}.
"""

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "{{project_slug}}"
    assert "version" in data


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "{{project_slug}}"


def test_readiness_check():
    """Test readiness check endpoint."""
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"


def test_status_endpoint():
    """Test status endpoint."""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["service"] == "{{project_slug}}"


def test_metrics_endpoint():
    """Test metrics endpoint."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text


def test_404_error():
    """Test 404 error handling."""
    response = client.get("/nonexistent")
    assert response.status_code == 404
