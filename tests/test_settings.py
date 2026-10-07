import pytest
from pydantic import ValidationError
from sqlalchemy import make_url

from app.config import Settings

OPTIONAL_VARS = [
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "LLM_PROVIDER",
    "LLM_MODEL",
    "MAX_TOOL_ROUNDS",
    "GRAPH_RECURSION_LIMIT",
    "INVESTIGATION_TIMEOUT_SECONDS",
    "LLM_REQUEST_TIMEOUT_SECONDS",
]


@pytest.fixture
def required_env(monkeypatch):
    for name in OPTIONAL_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("POSTGRES_DB", "incident_agent")
    monkeypatch.setenv("POSTGRES_USER", "incident_agent")
    monkeypatch.setenv("POSTGRES_PASSWORD", "incident_agent_dev")
    return monkeypatch


def test_optional_settings_use_proposal_defaults(required_env):
    settings = Settings()

    assert settings.llm_provider == "ollama"
    assert settings.llm_model == "llama3.2:3b"
    assert settings.max_tool_rounds == 2
    assert settings.graph_recursion_limit == 16
    assert settings.investigation_timeout_seconds == 300
    assert settings.llm_request_timeout_seconds == 120


def test_ollama_provider_is_accepted(required_env):
    required_env.setenv("LLM_PROVIDER", "ollama")

    assert Settings().llm_provider == "ollama"


def test_unsupported_llm_provider_is_rejected(required_env):
    required_env.setenv("LLM_PROVIDER", "openai")

    with pytest.raises(ValidationError, match="llm_provider"):
        Settings()


def test_database_url_round_trips_special_characters_in_password(required_env):
    required_env.setenv("POSTGRES_PASSWORD", "p@ss:w/rd#?%")

    url = make_url(Settings().database_url)

    assert url.drivername == "postgresql+psycopg"
    assert url.username == "incident_agent"
    assert url.password == "p@ss:w/rd#?%"
    assert url.host == "db"
    assert url.port == 5432
    assert url.database == "incident_agent"
