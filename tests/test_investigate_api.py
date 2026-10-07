from datetime import datetime

from fastapi.testclient import TestClient

from app.main import create_app

from tests.fakes import calls_tools, finishes, returns_report, tool_call
from tests.scenarios import CHECKOUT, CHECKOUT_LINES, POOL_REPORT

QUERY_CHECKOUT = calls_tools(tool_call("query_logs", {"service": "checkout"}, "call-1"))


def create_checkout_incident(client) -> int:
    response = client.post(
        "/incidents", json={"title": CHECKOUT.title, "description": CHECKOUT.description}
    )
    return response.json()["id"]


def test_investigate_returns_completed_report(client_with_models):
    client = client_with_models([QUERY_CHECKOUT, finishes()], [returns_report(POOL_REPORT)])
    incident_id = create_checkout_incident(client)

    response = client.post(f"/incidents/{incident_id}/investigate")

    assert response.status_code == 200
    body = response.json()
    assert body["incident_id"] == incident_id
    assert isinstance(body["report_id"], int)
    assert body["status"] == "completed"
    assert body["report"] == POOL_REPORT


def test_successful_investigation_marks_incident_completed(client_with_models):
    client = client_with_models([QUERY_CHECKOUT, finishes()], [returns_report(POOL_REPORT)])
    incident_id = create_checkout_incident(client)

    client.post(f"/incidents/{incident_id}/investigate")

    assert client.get(f"/incidents/{incident_id}").json()["status"] == "completed"


def test_latest_report_carries_report_evidence_and_tool_calls(client_with_models):
    client = client_with_models([QUERY_CHECKOUT, finishes()], [returns_report(POOL_REPORT)])
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
    client = client_with_models([QUERY_CHECKOUT, finishes()], [returns_report(POOL_REPORT)])
    incident_id = create_checkout_incident(client)
    client.post(f"/incidents/{incident_id}/investigate")

    latest = client.get(f"/incidents/{incident_id}").json()["latest_report"]

    assert latest["model_name"] == settings.llm_model


def test_saved_report_is_visible_from_a_new_application_instance(client_with_models, settings):
    client = client_with_models([QUERY_CHECKOUT, finishes()], [returns_report(POOL_REPORT)])
    incident_id = create_checkout_incident(client)
    report_id = client.post(f"/incidents/{incident_id}/investigate").json()["report_id"]

    with TestClient(create_app(settings)) as other_client:
        latest = other_client.get(f"/incidents/{incident_id}").json()["latest_report"]

    assert latest["id"] == report_id
    assert latest["report"] == POOL_REPORT


def test_second_investigation_becomes_the_latest_report(client_with_models):
    client = client_with_models(
        [QUERY_CHECKOUT, finishes(), QUERY_CHECKOUT, finishes()],
        [returns_report(POOL_REPORT), returns_report(POOL_REPORT)],
    )
    incident_id = create_checkout_incident(client)

    first_id = client.post(f"/incidents/{incident_id}/investigate").json()["report_id"]
    second_id = client.post(f"/incidents/{incident_id}/investigate").json()["report_id"]

    assert second_id > first_id
    assert client.get(f"/incidents/{incident_id}").json()["latest_report"]["id"] == second_id
