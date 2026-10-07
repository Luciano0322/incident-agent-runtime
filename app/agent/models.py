from dataclasses import dataclass

import httpx
import ollama
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from app.config import Settings

# Errors that mean the model provider failed. Kept narrow on purpose: anything
# else is a bug and should surface as a 500, not a provider failure.
PROVIDER_ERRORS: tuple[type[BaseException], ...] = (
    ConnectionError,
    ollama.ResponseError,
    httpx.TransportError,
)


@dataclass(frozen=True)
class ChatModels:
    agent: BaseChatModel
    report: BaseChatModel


def build_chat_models(
    settings: Settings, transport: httpx.AsyncBaseTransport | None = None
) -> ChatModels:
    """Two Ollama adapters for the same model: one binds tools, one writes the report.

    `transport` replaces the HTTP layer in tests.
    """
    client_kwargs: dict = {"timeout": settings.llm_request_timeout_seconds}
    if transport is not None:
        client_kwargs["transport"] = transport

    def adapter() -> ChatOllama:
        return ChatOllama(
            model=settings.llm_model,
            base_url=settings.ollama_base_url,
            temperature=0,
            async_client_kwargs=client_kwargs,
        )

    return ChatModels(agent=adapter(), report=adapter())
