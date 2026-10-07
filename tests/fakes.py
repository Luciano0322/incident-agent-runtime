"""Scripted chat models that stand in for the LLM at the model boundary."""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


@dataclass
class Slow:
    """Reply with `message` after sleeping `seconds`."""

    seconds: float
    message: AIMessage


class ScriptedChatModel(BaseChatModel):
    """Returns scripted replies in order and records every input it receives.

    A reply may be an AIMessage, an exception to raise, or Slow(...).
    Pass `respond` instead to compute each reply from the input messages.
    """

    replies: list[Any] = []
    respond: Callable[[list[BaseMessage]], AIMessage] | None = None
    received: list[list[BaseMessage]] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ScriptedChatModel":
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        raise NotImplementedError("ScriptedChatModel is async-only")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.received.append(list(messages))
        reply = self.respond(messages) if self.respond else self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        if isinstance(reply, Slow):
            await asyncio.sleep(reply.seconds)
            reply = reply.message
        return ChatResult(generations=[ChatGeneration(message=reply)])


def tool_call(name: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


def calls_tools(*calls: dict[str, Any]) -> AIMessage:
    return AIMessage(content="", tool_calls=list(calls))


def finishes() -> AIMessage:
    return AIMessage(content="I have enough evidence.")


def returns_report(report: dict[str, Any]) -> AIMessage:
    """How a tool-calling model answers with_structured_output(InvestigationReport)."""
    return calls_tools(tool_call("InvestigationReport", report, "report-1"))


class FakeModelRegistry:
    """In-memory stand-in for the Ollama model registry."""

    def __init__(
        self, models=(), reachable=True, pull_installs=True, unreachable_calls=0, pull_error=None
    ):
        self.models = list(models)
        self.pull_error = pull_error
        self.reachable = reachable
        self.unreachable_calls = unreachable_calls
        self.pull_installs = pull_installs
        self.pulled: list[str] = []

    async def list_models(self) -> list[str]:
        if self.unreachable_calls:
            self.unreachable_calls -= 1
            raise ConnectionError("Failed to connect to Ollama")
        if not self.reachable:
            raise ConnectionError("Failed to connect to Ollama")
        return list(self.models)

    async def pull(self, model: str) -> None:
        if not self.reachable:
            raise ConnectionError("Failed to connect to Ollama")
        self.pulled.append(model)
        if self.pull_error is not None:
            raise self.pull_error
        if self.pull_installs:
            self.models.append(model)
