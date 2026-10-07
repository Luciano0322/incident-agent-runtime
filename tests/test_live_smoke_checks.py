import copy

from scripts.live_smoke import check_checkout_investigation
from tests.scenarios import CHECKOUT_LINES, POOL_REPORT

INVESTIGATED = {"incident_id": 1, "report_id": 7, "status": "completed", "report": POOL_REPORT}
FETCHED = {
    "id": 1,
    "status": "completed",
    "latest_report": {
        "id": 7,
        "created_at": "2026-10-07T08:00:00+00:00",
        "report": POOL_REPORT,
        "evidence": CHECKOUT_LINES,
        "tool_calls": [{"name": "query_logs", "args": {"service": "checkout", "keyword": None}}],
        "model_name": "llama3.2:3b",
    },
}


def test_a_grounded_checkout_investigation_passes():
    assert check_checkout_investigation(INVESTIGATED, FETCHED) == []


def test_missing_checkout_query_is_reported():
    fetched = copy.deepcopy(FETCHED)
    fetched["latest_report"]["tool_calls"] = []

    problems = check_checkout_investigation(INVESTIGATED, fetched)

    assert any("query_logs" in problem for problem in problems)


def test_report_without_hypotheses_or_next_steps_is_reported():
    empty = {**POOL_REPORT, "hypotheses": [], "recommended_next_steps": []}
    fetched = copy.deepcopy(FETCHED)
    fetched["latest_report"]["report"] = empty

    problems = check_checkout_investigation({**INVESTIGATED, "report": empty}, fetched)

    assert any("hypothes" in problem for problem in problems)
    assert any("next step" in problem for problem in problems)


def test_report_changed_between_investigate_and_get_is_reported():
    fetched = copy.deepcopy(FETCHED)
    fetched["latest_report"]["id"] = 8

    problems = check_checkout_investigation(INVESTIGATED, fetched)

    assert any("GET" in problem for problem in problems)
