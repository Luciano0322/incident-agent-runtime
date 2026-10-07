from tests.fakes import calls_tools, finishes, returns_report, tool_call
from tests.scenarios import CHECKOUT, POOL_REPORT

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
