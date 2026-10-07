from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_returns_200_without_database_or_model():
    settings = Settings(
        postgres_db="unused",
        postgres_user="unused",
        postgres_password="unused",
        postgres_host="unreachable.invalid",
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/health")

    assert response.status_code == 200
