import json
from dataclasses import dataclass
from typing import Annotated, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from app.agent import prompts
from app.schemas.investigation import InvestigationInput, InvestigationResult, ToolCallRecord
from app.schemas.report import InvestigationReport
from app.tools.registry import default_tools


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
        state = await self._graph.ainvoke(
            {"incident": incident, "messages": [], "evidence": [], "tool_calls": [], "report": None}
        )
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
        reply = await self._agent.ainvoke(state["messages"])
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
            tool = self._tools[call["name"]]
            args = tool.args_schema.model_validate(call["args"])
            lines = tool.func(**args.model_dump())
            evidence.extend(line for line in lines if line not in evidence)
            records.append(ToolCallRecord(name=call["name"], args=args.model_dump()))
            messages.append(
                ToolMessage(json.dumps(lines), tool_call_id=call["id"], name=call["name"])
            )
        return {"messages": messages, "evidence": evidence, "tool_calls": records}

    async def _write_report(self, state: InvestigationState) -> dict:
        report = await self._report.ainvoke(
            [
                SystemMessage(prompts.REPORT_SYSTEM),
                HumanMessage(prompts.report_request(state["incident"], state["evidence"])),
            ]
        )
        return {"report": report}


def build_investigator(
    agent_model: BaseChatModel,
    report_model: BaseChatModel,
    limits: InvestigationLimits = InvestigationLimits(),
) -> Investigator:
    return Investigator(agent_model, report_model, limits)
