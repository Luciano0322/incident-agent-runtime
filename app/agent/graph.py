import asyncio
import json
from dataclasses import dataclass
from typing import Annotated, TypedDict

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import ValidationError

from app.agent import prompts
from app.agent.errors import (
    DeadlineExceeded,
    InvalidStructuredOutput,
    LoopLimitExceeded,
    ProviderFailure,
    ToolCallError,
)
from app.agent.grounding import validate_grounding
from app.schemas.investigation import InvestigationInput, InvestigationResult, ToolCallRecord
from app.schemas.report import InvestigationReport
from app.tools.registry import default_tools

MAX_TOOL_CALLS_PER_ROUND = 2

# Errors that mean the model provider failed. Kept narrow on purpose: anything
# else is a bug and should surface as a 500, not a provider failure.
PROVIDER_ERRORS: tuple[type[BaseException], ...] = (ConnectionError,)


@dataclass(frozen=True)
class InvestigationLimits:
    max_tool_rounds: int = 2
    graph_recursion_limit: int = 16
    timeout_seconds: float = 300


class InvestigationState(TypedDict):
    incident: InvestigationInput
    messages: Annotated[list[AnyMessage], add_messages]
    evidence: list[str]
    tool_calls: list[ToolCallRecord]
    tool_rounds: int
    report: InvestigationReport | None


class Investigator:
    def __init__(
        self,
        agent_model: BaseChatModel,
        report_model: BaseChatModel,
        limits: InvestigationLimits,
    ) -> None:
        self._tools = default_tools()
        self._agent = agent_model.bind_tools(list(self._tools.values()))
        self._report = report_model.with_structured_output(InvestigationReport)
        self._limits = limits
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(InvestigationState)
        graph.add_node("analyze", self._analyze)
        graph.add_node("agent", self._call_agent)
        graph.add_node("tools", self._run_tools)
        graph.add_node("report", self._write_report)
        graph.add_edge(START, "analyze")
        graph.add_edge("analyze", "agent")
        graph.add_conditional_edges("agent", self._route_after_agent, ["tools", "report"])
        graph.add_edge("tools", "agent")
        graph.add_edge("report", END)
        return graph.compile()

    async def investigate(self, incident: InvestigationInput) -> InvestigationResult:
        initial = {
            "incident": incident,
            "messages": [],
            "evidence": [],
            "tool_calls": [],
            "tool_rounds": 0,
            "report": None,
        }
        try:
            async with asyncio.timeout(self._limits.timeout_seconds):
                state = await self._graph.ainvoke(
                    initial, config={"recursion_limit": self._limits.graph_recursion_limit}
                )
        except TimeoutError as exc:
            raise DeadlineExceeded(
                f"Investigation exceeded its {self._limits.timeout_seconds}s deadline"
            ) from exc
        except GraphRecursionError as exc:
            raise LoopLimitExceeded(
                f"Investigation hit the graph step limit of {self._limits.graph_recursion_limit}"
            ) from exc
        validate_grounding(state["report"], state["evidence"])
        return InvestigationResult(
            report=state["report"], evidence=state["evidence"], tool_calls=state["tool_calls"]
        )

    async def _analyze(self, state: InvestigationState) -> dict:
        incident = state["incident"]
        return {
            "messages": [
                SystemMessage(prompts.AGENT_SYSTEM),
                HumanMessage(prompts.incident_context(incident)),
            ]
        }

    async def _call_agent(self, state: InvestigationState) -> dict:
        try:
            reply = await self._agent.ainvoke(state["messages"])
        except PROVIDER_ERRORS as exc:
            raise ProviderFailure(f"Agent model call failed: {exc}") from exc
        if reply.tool_calls and state["tool_rounds"] >= self._limits.max_tool_rounds:
            raise LoopLimitExceeded(
                f"Model still requested tools after {self._limits.max_tool_rounds} tool rounds"
            )
        if len(reply.tool_calls) > MAX_TOOL_CALLS_PER_ROUND:
            raise LoopLimitExceeded(
                f"Model requested {len(reply.tool_calls)} tool calls in one round; "
                f"the limit is {MAX_TOOL_CALLS_PER_ROUND}"
            )
        return {"messages": [reply]}

    @staticmethod
    def _route_after_agent(state: InvestigationState) -> str:
        last = state["messages"][-1]
        return "tools" if isinstance(last, AIMessage) and last.tool_calls else "report"

    async def _run_tools(self, state: InvestigationState) -> dict:
        evidence = list(state["evidence"])
        records = list(state["tool_calls"])
        messages = []
        for call in state["messages"][-1].tool_calls:
            tool = self._tools.get(call["name"])
            if tool is None:
                raise ToolCallError(f"Model requested unknown tool {call['name']!r}")
            try:
                args = tool.args_schema.model_validate(call["args"])
            except ValidationError as exc:
                raise ToolCallError(f"Invalid arguments for {call['name']!r}: {exc}") from exc
            lines = tool.func(**args.model_dump())
            evidence.extend(line for line in lines if line not in evidence)
            records.append(ToolCallRecord(name=call["name"], args=args.model_dump()))
            messages.append(
                ToolMessage(json.dumps(lines), tool_call_id=call["id"], name=call["name"])
            )
        return {
            "messages": messages,
            "evidence": evidence,
            "tool_calls": records,
            "tool_rounds": state["tool_rounds"] + 1,
        }

    async def _write_report(self, state: InvestigationState) -> dict:
        try:
            report = await self._report.ainvoke(
                [
                    SystemMessage(prompts.REPORT_SYSTEM),
                    HumanMessage(prompts.report_request(state["incident"], state["evidence"])),
                ]
            )
        except PROVIDER_ERRORS as exc:
            raise ProviderFailure(f"Report model call failed: {exc}") from exc
        except (ValidationError, OutputParserException) as exc:
            raise InvalidStructuredOutput(f"Report model returned an invalid report: {exc}") from exc
        if not isinstance(report, InvestigationReport):
            raise InvalidStructuredOutput("Report model did not return a structured report")
        return {"report": report}


def build_investigator(
    agent_model: BaseChatModel,
    report_model: BaseChatModel,
    limits: InvestigationLimits = InvestigationLimits(),
) -> Investigator:
    return Investigator(agent_model, report_model, limits)
