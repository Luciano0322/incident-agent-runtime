from typing import Literal

from pydantic_settings import BaseSettings
from sqlalchemy import URL


class Settings(BaseSettings):
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_host: str = "db"
    postgres_port: int = 5432

    ollama_base_url: str = "http://ollama:11434"
    llm_provider: Literal["ollama"] = "ollama"
    llm_model: str = "qwen2.5:7b"
    max_tool_rounds: int = 2
    graph_recursion_limit: int = 16
    investigation_timeout_seconds: float = 600
    llm_request_timeout_seconds: float = 300

    @property
    def database_url(self) -> str:
        url = URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )
        return url.render_as_string(hide_password=False)
