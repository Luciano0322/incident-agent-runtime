import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.agent.models import ChatModels
from app.config import Settings
from app.db.migrations import alembic_config
from app.main import create_app
from tests.fakes import ScriptedChatModel


def run_migrations() -> None:
    command.upgrade(alembic_config(), "head")


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def database(settings):
    """Give each test an empty schema in test-db, migrated to head."""
    engine = create_engine(settings.database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    run_migrations()


@pytest.fixture
def client(settings, database):
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.fixture
def client_with_models(settings, database):
    """Build a client whose only substitution is the chat models."""
    clients = []

    def build(agent_replies, report_replies, settings=settings, **client_kwargs):
        models = ChatModels(
            agent=ScriptedChatModel(replies=list(agent_replies)),
            report=ScriptedChatModel(replies=list(report_replies)),
        )
        client = TestClient(create_app(settings, chat_models=models), **client_kwargs)
        clients.append(client.__enter__())
        return client

    yield build
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client_with_registry(settings, database):
    """Build a client whose Ollama model registry is an in-memory fake."""
    clients = []

    def build(registry, settings=settings, **client_kwargs):
        app = create_app(settings, model_registry=registry)
        client = TestClient(app, **client_kwargs)
        clients.append(client.__enter__())
        return client

    yield build
    for client in clients:
        client.__exit__(None, None, None)
