from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.main import create_app

from tests.fakes import Slow, calls_tools, finishes, returns_report, tool_call
from tests.scenarios import CHECKOUT, CHECKOUT_LINES, POOL_REPORT

def query_checkout():
    """A fresh message each time: LangGraph assigns IDs to messages in place."""
    return calls_tools(tool_call("query_logs", {"service": "checkout"}, "call-1"))


def create_checkout_incident(client) -> int:
    response = client.post(
        "/incidents", json={"title": CHECKOUT.title, "description": CHECKOUT.description}
    )
    return response.json()["id"]


def test_investigate_returns_completed_report(client_with_models):
    client = client_with_models([query_checkout(), finishes()], [returns_report(POOL_REPORT)])
    incident_id = create_checkout_incident(client)

    response = client.post(f"/incidents/{incident_id}/investigate")

    assert response.status_code == 200
    body = response.json()
    assert body["incident_id"] == incident_id
    assert isinstance(body["report_id"], int)
    assert body["status"] == "completed"
    assert body["report"] == POOL_REPORT


def test_successful_investigation_marks_incident_completed(client_with_models):
    client = client_with_models([query_checkout(), finishes()], [returns_report(POOL_REPORT)])
    incident_id = create_checkout_incident(client)

    client.post(f"/incidents/{incident_id}/investigate")

    assert client.get(f"/incidents/{incident_id}").json()["status"] == "completed"


def test_latest_report_carries_report_evidence_and_tool_calls(client_with_models):
    client = client_with_models([query_checkout(), finishes()], [returns_report(POOL_REPORT)])
    incident_id = create_checkout_incident(client)
    report_id = client.post(f"/incidents/{incident_id}/investigate").json()["report_id"]

    latest = client.get(f"/incidents/{incident_id}").json()["latest_report"]

    assert latest["id"] == report_id
    assert datetime.fromisoformat(latest["created_at"]).tzinfo is not None
    assert latest["report"] == POOL_REPORT
    assert latest["evidence"] == CHECKOUT_LINES
    assert latest["tool_calls"] == [
        {"name": "query_logs", "args": {"service": "checkout", "keyword": None}}
    ]


def test_saved_report_records_the_configured_model_name(client_with_models, settings):
    client = client_with_models([query_checkout(), finishes()], [returns_report(POOL_REPORT)])
    incident_id = create_checkout_incident(client)
    client.post(f"/incidents/{incident_id}/investigate")

    latest = client.get(f"/incidents/{incident_id}").json()["latest_report"]

    assert latest["model_name"] == settings.llm_model


def test_saved_report_is_visible_from_a_new_application_instance(client_with_models, settings):
    client = client_with_models([query_checkout(), finishes()], [returns_report(POOL_REPORT)])
    incident_id = create_checkout_incident(client)
    report_id = client.post(f"/incidents/{incident_id}/investigate").json()["report_id"]

    with TestClient(create_app(settings)) as other_client:
        latest = other_client.get(f"/incidents/{incident_id}").json()["latest_report"]

    assert latest["id"] == report_id
    assert latest["report"] == POOL_REPORT


def test_second_investigation_becomes_the_latest_report(client_with_models):
    client = client_with_models(
        [query_checkout(), finishes(), query_checkout(), finishes()],
        [returns_report(POOL_REPORT), returns_report(POOL_REPORT)],
    )
    incident_id = create_checkout_incident(client)

    first_id = client.post(f"/incidents/{incident_id}/investigate").json()["report_id"]
    second_id = client.post(f"/incidents/{incident_id}/investigate").json()["report_id"]

    assert second_id > first_id
    assert client.get(f"/incidents/{incident_id}").json()["latest_report"]["id"] == second_id


def test_investigating_a_missing_incident_returns_404(client_with_models):
    client = client_with_models([], [])

    response = client.post("/incidents/999999/investigate")

    assert response.status_code == 404
    assert response.json() == {"detail": "Incident not found"}


UNGROUNDED_REPORT = {
    **POOL_REPORT,
    "hypotheses": [
        {
            "cause": "Upstream payment timeout",
            "confidence": "medium",
            "evidence": ["15:01 payment-api ERROR upstream timeout"],
        }
    ],
}

FAILING_RUNS = {
    "provider-failure": ([ConnectionError("connection refused")], []),
    "invalid-structured-output": ([finishes()], [AIMessage(content="The database is slow.")]),
    "grounding-violation": ([query_checkout(), finishes()], [returns_report(UNGROUNDED_REPORT)]),
    "unknown-tool": ([calls_tools(tool_call("restart_service", {}, "c1"))], []),
    "invalid-tool-args": ([calls_tools(tool_call("query_logs", {"limit": 3}, "c1"))], []),
    "loop-limit": ([query_checkout(), query_checkout(), query_checkout()], []),
}


@pytest.mark.parametrize(("agent_replies", "report_replies"), FAILING_RUNS.values(), ids=FAILING_RUNS)
def test_expected_investigation_failures_return_502(client_with_models, agent_replies, report_replies):
    client = client_with_models(agent_replies, report_replies)
    incident_id = create_checkout_incident(client)

    response = client.post(f"/incidents/{incident_id}/investigate")

    assert response.status_code == 502


def test_investigation_past_its_deadline_returns_504(client_with_models, settings):
    client = client_with_models(
        [Slow(1.0, finishes())],
        [returns_report(POOL_REPORT)],
        settings=settings.model_copy(update={"investigation_timeout_seconds": 0.05}),
    )
    incident_id = create_checkout_incident(client)

    response = client.post(f"/incidents/{incident_id}/investigate")

    assert response.status_code == 504
