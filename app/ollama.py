from typing import Protocol

import ollama

from app.config import Settings


class ModelRegistry(Protocol):
    """The parts of the Ollama server that readiness and model-init rely on.

    Both methods raise ConnectionError when the server cannot be reached.
    """

    async def list_models(self) -> list[str]: ...

    async def pull(self, model: str) -> None: ...


def has_model(available: list[str], wanted: str) -> bool:
    """Match Ollama's naming, where an untagged name means the `latest` tag."""

    def normalize(name: str) -> str:
        return name if ":" in name else f"{name}:latest"

    return normalize(wanted) in {normalize(name) for name in available}


class OllamaModelRegistry:
    """ModelRegistry backed by the Ollama HTTP API."""

    def __init__(self, settings: Settings) -> None:
        self._client = ollama.AsyncClient(
            host=settings.ollama_base_url, timeout=settings.llm_request_timeout_seconds
        )

    async def list_models(self) -> list[str]:
        response = await self._client.list()
        return [model.model for model in response.models if model.model]

    async def pull(self, model: str) -> None:
        await self._client.pull(model)
