from typing import Protocol

import httpx
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

    def __init__(
        self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        extra = {"transport": transport} if transport is not None else {}
        self._client = ollama.AsyncClient(
            host=settings.ollama_base_url, timeout=settings.llm_request_timeout_seconds, **extra
        )

    async def list_models(self) -> list[str]:
        try:
            response = await self._client.list()
        except (ollama.ResponseError, httpx.TransportError) as exc:
            raise ConnectionError(f"Ollama could not list models: {exc}") from exc
        return [model.model for model in response.models if model.model]

    async def pull(self, model: str) -> None:
        """Stream the pull so a long download never trips the read timeout."""
        last_status = None
        try:
            async for progress in await self._client.pull(model, stream=True):
                if progress.status != last_status:
                    print(f"{model}: {progress.status}", flush=True)
                    last_status = progress.status
        except (ollama.ResponseError, httpx.TransportError) as exc:
            raise ConnectionError(f"Ollama could not pull {model}: {exc}") from exc
