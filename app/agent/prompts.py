from app.schemas.investigation import InvestigationInput

AGENT_SYSTEM = """You are an incident investigator.
Decide whether you need log evidence. To collect it, call the query_logs tool
with the service name and an optional keyword. Known services: checkout, payment.
When you have enough evidence, or none is relevant, reply without calling tools.
Do not write the final report."""

REPORT_SYSTEM = """You write a structured incident investigation report.
Every evidence entry must be copied exactly, as a whole line, from the collected
log lines below. Never cite the incident description or anything not listed.
If no log lines were collected, return an empty hypotheses list and still give a
clear summary and next steps."""


def incident_context(incident: InvestigationInput) -> str:
    return f"Incident: {incident.title}\n\n{incident.description}"


def report_request(incident: InvestigationInput, evidence: list[str]) -> str:
    lines = "\n".join(evidence) if evidence else "(no log lines were collected)"
    return f"{incident_context(incident)}\n\nCollected log lines:\n{lines}"
