import json

from langchain_core.messages import ToolMessage

from app.agent.graph import build_investigator
from app.schemas.investigation import InvestigationInput, InvestigationResult
from tests.fakes import ScriptedChatModel, calls_tools, finishes, returns_report, tool_call

CHECKOUT = InvestigationInput(
    incident_id=1,
    title="Checkout API latency spike",
    description="Checkout API latency increased significantly after 14:20.",
)

NO_EVIDENCE_REPORT = {
    "summary": "No log evidence was collected.",
    "hypotheses": [],
    "recommended_next_steps": ["Identify the affected service and query its logs"],
}


async def test_agent_without_tool_calls_goes_straight_to_report():
    investigator = build_investigator(
        agent_model=ScriptedChatModel(replies=[finishes()]),
        report_model=ScriptedChatModel(replies=[returns_report(NO_EVIDENCE_REPORT)]),
    )

    result = await investigator.investigate(CHECKOUT)

    assert result.report.summary == "No log evidence was collected."
    assert result.evidence == []
    assert result.tool_calls == []

CHECKOUT_LINES = [
    "14:21 checkout-api ERROR database connection timeout",
    "14:22 checkout-api ERROR connection pool exhausted",
    "14:24 checkout-api WARN retrying database request",
]

POOL_REPORT = {
    "summary": "Checkout latency may be related to database connection pool exhaustion.",
    "hypotheses": [
        {
            "cause": "Database connection pool exhaustion",
            "confidence": "high",
            "evidence": [
                "14:21 checkout-api ERROR database connection timeout",
                "14:22 checkout-api ERROR connection pool exhausted",
            ],
        }
    ],
    "recommended_next_steps": ["Inspect active database connections"],
}


async def test_one_query_logs_call_collects_evidence_and_records_the_call():
    investigator = build_investigator(
        agent_model=ScriptedChatModel(
            replies=[
                calls_tools(tool_call("query_logs", {"service": "checkout"}, "call-1")),
                finishes(),
            ]
        ),
        report_model=ScriptedChatModel(replies=[returns_report(POOL_REPORT)]),
    )

    result = await investigator.investigate(CHECKOUT)

    assert result.evidence == CHECKOUT_LINES
    assert [(c.name, c.args) for c in result.tool_calls] == [
        ("query_logs", {"service": "checkout", "keyword": None})
    ]
    assert result.report.hypotheses[0].cause == "Database connection pool exhaustion"


async def test_agent_receives_tool_result_paired_with_its_call_id():
    agent = ScriptedChatModel(
        replies=[
            calls_tools(tool_call("query_logs", {"service": "checkout"}, "call-1")),
            finishes(),
        ]
    )
    investigator = build_investigator(
        agent_model=agent,
        report_model=ScriptedChatModel(replies=[returns_report(POOL_REPORT)]),
    )

    await investigator.investigate(CHECKOUT)

    tool_result = agent.received[1][-1]
    assert isinstance(tool_result, ToolMessage)
    assert tool_result.tool_call_id == "call-1"
    assert "14:22 checkout-api ERROR connection pool exhausted" in tool_result.content


async def test_two_rounds_accumulate_evidence_without_duplicate_lines():
    investigator = build_investigator(
        agent_model=ScriptedChatModel(
            replies=[
                calls_tools(tool_call("query_logs", {"service": "checkout", "keyword": "pool"}, "c1")),
                calls_tools(tool_call("query_logs", {"service": "checkout"}, "c2")),
                finishes(),
            ]
        ),
        report_model=ScriptedChatModel(replies=[returns_report(POOL_REPORT)]),
    )

    result = await investigator.investigate(CHECKOUT)

    assert result.evidence == [
        "14:22 checkout-api ERROR connection pool exhausted",
        "14:21 checkout-api ERROR database connection timeout",
        "14:24 checkout-api WARN retrying database request",
    ]
    assert len(result.tool_calls) == 2


async def test_report_model_sees_exactly_the_collected_evidence():
    report_model = ScriptedChatModel(replies=[returns_report(POOL_REPORT)])
    investigator = build_investigator(
        agent_model=ScriptedChatModel(
            replies=[
                calls_tools(tool_call("query_logs", {"service": "checkout", "keyword": "ERROR"}, "c1")),
                finishes(),
            ]
        ),
        report_model=report_model,
    )

    result = await investigator.investigate(CHECKOUT)

    report_prompt = report_model.received[0][-1].content
    for line in result.evidence:
        assert line in report_prompt
    assert "14:24 checkout-api WARN retrying database request" not in report_prompt


async def test_result_round_trips_through_json_without_framework_types():
    investigator = build_investigator(
        agent_model=ScriptedChatModel(
            replies=[
                calls_tools(tool_call("query_logs", {"service": "checkout"}, "call-1")),
                finishes(),
            ]
        ),
        report_model=ScriptedChatModel(replies=[returns_report(POOL_REPORT)]),
    )

    result = await investigator.investigate(CHECKOUT)

    payload = json.loads(result.model_dump_json())
    assert payload["evidence"] == CHECKOUT_LINES
    assert payload["tool_calls"] == [
        {"name": "query_logs", "args": {"service": "checkout", "keyword": None}}
    ]
    assert InvestigationResult.model_validate(payload) == result
