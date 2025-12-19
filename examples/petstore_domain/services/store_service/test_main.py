import pytest
from fastapi.testclient import TestClient

from examples.petstore_domain.services.store_service.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"

def test_catalog(client):
    response = client.get("/store/catalog")
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) >= 3
    assert any(item["pet_id"] == "corgi" for item in items)
