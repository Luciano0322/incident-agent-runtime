from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel

from app.config import Settings


@dataclass(frozen=True)
class ChatModels:
    agent: BaseChatModel
    report: BaseChatModel


def build_chat_models(settings: Settings) -> ChatModels:
    raise NotImplementedError("The Ollama chat model adapter is added in M4")
