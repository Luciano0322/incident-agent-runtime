from app.schemas.investigation import InvestigationInput

AGENT_SYSTEM = """You are an incident investigator.
When the incident concerns a known service, collect log evidence with the
query_logs tool before concluding. Known services: checkout, payment.
query_logs(service) returns every log line for that service. The optional keyword
only keeps lines whose text contains it (for example "timeout" or "pool"); it is
not a time filter, so never pass a time as the keyword. Start without a keyword.
If a query returns no lines, query again without a keyword.
When you have enough evidence, reply without calling tools.
Do not write the final report."""

REPORT_SYSTEM = """You write a structured incident investigation report.
Every evidence entry must be copied exactly, as a whole line, from the collected
log lines below. Never cite the incident description or anything not listed.
If log lines were collected, give at least one hypothesis that cites the lines
that support it. If no log lines were collected, return an empty hypotheses list
and still give a clear summary and next steps."""


def incident_context(incident: InvestigationInput) -> str:
    return f"Incident: {incident.title}\n\n{incident.description}"


def report_request(incident: InvestigationInput, evidence: list[str]) -> str:
    lines = "\n".join(evidence) if evidence else "(no log lines were collected)"
    return f"{incident_context(incident)}\n\nCollected log lines:\n{lines}"
