"""End-to-end check against a running API with a real model.

Run inside the api container: `python -m scripts.live_smoke`. It creates the
checkout incident, investigates it, reads it back, and checks the result.
Exits non-zero when any check fails. A pass shows the flow works end to end
once; it does not mean every future inference will succeed.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

from pydantic import ValidationError

from app.schemas.report import InvestigationReport

CHECKOUT_INCIDENT = {
    "title": "Checkout API latency spike",
    "description": "Checkout API latency increased significantly after 14:20.",
}


def check_checkout_investigation(investigated: dict, fetched: dict) -> list[str]:
    """Return every way the checkout investigation falls short; empty means it passed."""
    problems = []
    latest = fetched.get("latest_report") or {}

    calls = latest.get("tool_calls", [])
    if not any(
        call["name"] == "query_logs" and call["args"].get("service") == "checkout"
        for call in calls
    ):
        problems.append(f'model did not call query_logs(service="checkout"); calls: {calls}')

    try:
        report = InvestigationReport.model_validate(investigated.get("report"))
    except ValidationError as exc:
        return [*problems, f"report does not match the schema: {exc}"]

    if not report.hypotheses:
        problems.append("report has no hypotheses")
    if not report.recommended_next_steps:
        problems.append("report has no recommended next steps")

    evidence = set(latest.get("evidence", []))
    for hypothesis in report.hypotheses:
        for line in hypothesis.evidence:
            if line not in evidence:
                problems.append(f"cited evidence was not returned by the tool: {line!r}")

    if latest.get("id") != investigated.get("report_id") or latest.get("report") != investigated.get(
        "report"
    ):
        problems.append("GET /incidents/{id} did not return the report that was just saved")
    return problems


def request(method: str, url: str, body: dict | None = None, timeout: float = 30) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read())


def main() -> None:
    base = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
    investigate_timeout = float(os.environ.get("INVESTIGATION_TIMEOUT_SECONDS", "300")) + 30

    try:
        incident = request("POST", f"{base}/incidents", CHECKOUT_INCIDENT)
        started = time.monotonic()
        investigated = request(
            "POST", f"{base}/incidents/{incident['id']}/investigate", timeout=investigate_timeout
        )
        elapsed = time.monotonic() - started
        fetched = request("GET", f"{base}/incidents/{incident['id']}")
    except urllib.error.HTTPError as exc:
        print(f"FAIL: {exc.code} from {exc.url}: {exc.read().decode(errors='replace')}")
        sys.exit(1)

    latest = fetched["latest_report"] or {}
    print(f"incident {incident['id']}, report {investigated['report_id']}, {elapsed:.1f}s")
    print(f"model: {latest.get('model_name')}")
    print(f"tool calls: {json.dumps(latest.get('tool_calls'))}")
    print(f"report: {json.dumps(investigated['report'], indent=2)}")

    problems = check_checkout_investigation(investigated, fetched)
    for problem in problems:
        print(f"FAIL: {problem}")
    if problems:
        sys.exit(1)
    print("PASS: checkout investigation is grounded and saved. Review the hypotheses by hand.")


if __name__ == "__main__":
    main()
