from alembic import command
from fastapi.testclient import TestClient

from app.agent.models import ChatModels
from app.db.migrations import alembic_config
from app.main import create_app
from tests.fakes import FakeModelRegistry, ScriptedChatModel


def test_ready_when_database_migrations_ollama_and_model_are_available(
    client_with_registry, settings
):
    client = client_with_registry(FakeModelRegistry(models=[settings.llm_model]))

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_not_ready_when_ollama_is_unreachable(client_with_registry):
    client = client_with_registry(FakeModelRegistry(reachable=False))

    response = client.get("/ready")

    assert response.status_code == 503
    assert "ollama" in response.json()["checks"]


def test_not_ready_when_configured_model_is_missing(client_with_registry):
    client = client_with_registry(FakeModelRegistry(models=["some-other-model:1b"]))

    response = client.get("/ready")

    assert response.status_code == 503
    assert "model" in response.json()["checks"]


def test_not_ready_when_database_is_unreachable(client_with_registry, settings):
    client = client_with_registry(
        FakeModelRegistry(models=[settings.llm_model]),
        settings=settings.model_copy(update={"postgres_port": 1}),
    )

    response = client.get("/ready")

    assert response.status_code == 503
    assert "database" in response.json()["checks"]


def test_not_ready_when_schema_is_behind_the_code(client_with_registry, settings):
    command.downgrade(alembic_config(), "0001")
    client = client_with_registry(FakeModelRegistry(models=[settings.llm_model]))

    response = client.get("/ready")

    assert response.status_code == 503
    assert "migrations" in response.json()["checks"]


def test_readiness_does_not_run_inference(settings, database):
    agent, report = ScriptedChatModel(), ScriptedChatModel()
    app = create_app(
        settings,
        chat_models=ChatModels(agent=agent, report=report),
        model_registry=FakeModelRegistry(models=[settings.llm_model]),
    )

    with TestClient(app) as client:
        assert client.get("/ready").status_code == 200

    assert agent.received == []
    assert report.received == []
