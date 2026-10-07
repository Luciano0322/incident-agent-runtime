import asyncio
import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.agent.errors import (
    DeadlineExceeded,
    GroundingViolation,
    InvalidStructuredOutput,
    LoopLimitExceeded,
    ProviderFailure,
    ToolCallError,
)
from app.agent.graph import InvestigationLimits, build_investigator
from app.schemas.investigation import InvestigationInput, InvestigationResult
from tests.fakes import Slow, ScriptedChatModel, calls_tools, finishes, returns_report, tool_call
from tests.scenarios import CHECKOUT, CHECKOUT_LINES, NO_EVIDENCE_REPORT, POOL_REPORT



async def test_agent_without_tool_calls_goes_straight_to_report():
    investigator = build_investigator(
        agent_model=ScriptedChatModel(replies=[finishes()]),
        report_model=ScriptedChatModel(replies=[returns_report(NO_EVIDENCE_REPORT)]),
    )

    result = await investigator.investigate(CHECKOUT)

    assert result.report.summary == "No log evidence was collected."
    assert result.evidence == []
    assert result.tool_calls == []

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


def investigator_with_agent_replies(*replies, report=POOL_REPORT, **kwargs):
    return build_investigator(
        agent_model=ScriptedChatModel(replies=list(replies)),
        report_model=ScriptedChatModel(replies=[returns_report(report)]),
        **kwargs,
    )


async def test_unknown_tool_is_reported_as_tool_call_error():
    investigator = investigator_with_agent_replies(
        calls_tools(tool_call("restart_service", {"service": "checkout"}, "c1")),
        finishes(),
    )

    with pytest.raises(ToolCallError, match="restart_service"):
        await investigator.investigate(CHECKOUT)


@pytest.mark.parametrize(
    "args",
    [{}, {"service": 42}, {"service": "checkout", "limit": 10}],
    ids=["missing-service", "wrong-type", "unexpected-arg"],
)
async def test_invalid_tool_arguments_are_reported_as_tool_call_error(args):
    investigator = investigator_with_agent_replies(
        calls_tools(tool_call("query_logs", args, "c1")),
        finishes(),
    )

    with pytest.raises(ToolCallError, match="query_logs"):
        await investigator.investigate(CHECKOUT)


def query_checkout(call_id: str):
    return calls_tools(tool_call("query_logs", {"service": "checkout"}, call_id))


async def test_tool_request_after_max_rounds_is_a_loop_limit_failure():
    report_model = ScriptedChatModel(replies=[returns_report(POOL_REPORT)])
    investigator = build_investigator(
        agent_model=ScriptedChatModel(
            replies=[query_checkout("c1"), query_checkout("c2"), query_checkout("c3"), finishes()]
        ),
        report_model=report_model,
        limits=InvestigationLimits(max_tool_rounds=2),
    )

    with pytest.raises(LoopLimitExceeded):
        await investigator.investigate(CHECKOUT)
    assert report_model.received == []


async def test_more_than_two_tool_calls_in_one_round_is_rejected():
    investigator = investigator_with_agent_replies(
        calls_tools(
            tool_call("query_logs", {"service": "checkout"}, "c1"),
            tool_call("query_logs", {"service": "payment"}, "c2"),
            tool_call("query_logs", {"service": "checkout", "keyword": "pool"}, "c3"),
        ),
        finishes(),
    )

    with pytest.raises(LoopLimitExceeded, match="3 tool calls"):
        await investigator.investigate(CHECKOUT)


async def test_two_tool_calls_in_one_round_are_allowed():
    investigator = investigator_with_agent_replies(
        calls_tools(
            tool_call("query_logs", {"service": "checkout"}, "c1"),
            tool_call("query_logs", {"service": "payment"}, "c2"),
        ),
        finishes(),
    )

    result = await investigator.investigate(CHECKOUT)

    assert len(result.tool_calls) == 2


async def test_graph_recursion_limit_is_reported_as_loop_limit():
    investigator = investigator_with_agent_replies(
        query_checkout("c1"),
        finishes(),
        limits=InvestigationLimits(graph_recursion_limit=3),
    )

    with pytest.raises(LoopLimitExceeded, match="graph step limit"):
        await investigator.investigate(CHECKOUT)


@pytest.mark.parametrize(
    "reply",
    [
        returns_report({**POOL_REPORT, "hypotheses": [{**POOL_REPORT["hypotheses"][0], "confidence": "certain"}]}),
        returns_report({"summary": "Missing the other fields."}),
        AIMessage(content="Here is my report: the database is slow."),
    ],
    ids=["bad-confidence", "missing-fields", "no-structured-reply"],
)
async def test_invalid_report_output_is_reported(reply):
    investigator = build_investigator(
        agent_model=ScriptedChatModel(replies=[query_checkout("c1"), finishes()]),
        report_model=ScriptedChatModel(replies=[reply]),
    )

    with pytest.raises(InvalidStructuredOutput):
        await investigator.investigate(CHECKOUT)


async def test_report_citing_evidence_that_was_not_collected_is_a_grounding_violation():
    ungrounded = {
        **POOL_REPORT,
        "hypotheses": [
            {
                "cause": "Upstream payment timeout",
                "confidence": "medium",
                "evidence": ["15:01 payment-api ERROR upstream timeout"],
            }
        ],
    }
    investigator = investigator_with_agent_replies(query_checkout("c1"), finishes(), report=ungrounded)

    with pytest.raises(GroundingViolation, match="15:01 payment-api ERROR upstream timeout"):
        await investigator.investigate(CHECKOUT)


async def test_investigation_past_its_deadline_is_reported():
    investigator = build_investigator(
        agent_model=ScriptedChatModel(replies=[Slow(1.0, finishes())]),
        report_model=ScriptedChatModel(replies=[returns_report(NO_EVIDENCE_REPORT)]),
        limits=InvestigationLimits(timeout_seconds=0.05),
    )

    with pytest.raises(DeadlineExceeded):
        await investigator.investigate(CHECKOUT)


async def test_agent_model_connection_error_is_a_provider_failure():
    investigator = investigator_with_agent_replies(ConnectionError("connection refused"))

    with pytest.raises(ProviderFailure):
        await investigator.investigate(CHECKOUT)


async def test_report_model_connection_error_is_a_provider_failure():
    investigator = build_investigator(
        agent_model=ScriptedChatModel(replies=[finishes()]),
        report_model=ScriptedChatModel(replies=[ConnectionError("connection reset")]),
    )

    with pytest.raises(ProviderFailure):
        await investigator.investigate(CHECKOUT)


async def test_sequential_runs_on_one_graph_do_not_share_state():
    investigator = build_investigator(
        agent_model=ScriptedChatModel(replies=[query_checkout("c1"), finishes(), finishes()]),
        report_model=ScriptedChatModel(
            replies=[returns_report(POOL_REPORT), returns_report(NO_EVIDENCE_REPORT)]
        ),
    )

    first = await investigator.investigate(CHECKOUT)
    second = await investigator.investigate(CHECKOUT)

    assert first.evidence == CHECKOUT_LINES
    assert second.evidence == []
    assert second.tool_calls == []


def query_the_service_named_in_the_incident(messages):
    if isinstance(messages[-1], ToolMessage):
        return finishes()
    service = "payment" if "Payment" in messages[-1].content else "checkout"
    return calls_tools(tool_call("query_logs", {"service": service}, f"call-{service}"))


async def test_concurrent_runs_keep_their_evidence_separate():
    payment = InvestigationInput(
        incident_id=2, title="Payment API errors", description="Payment API timeouts since 15:00."
    )
    investigator = build_investigator(
        agent_model=ScriptedChatModel(respond=query_the_service_named_in_the_incident),
        report_model=ScriptedChatModel(respond=lambda _: returns_report(NO_EVIDENCE_REPORT)),
    )

    checkout_result, payment_result = await asyncio.gather(
        investigator.investigate(CHECKOUT), investigator.investigate(payment)
    )

    assert checkout_result.evidence == CHECKOUT_LINES
    assert payment_result.evidence == [
        "15:01 payment-api ERROR upstream timeout",
        "15:02 payment-api WARN retry request",
    ]
