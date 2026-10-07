import json
from pathlib import Path

LOGS_PATH = Path(__file__).resolve().parents[2] / "data" / "logs.json"


def query_logs(service: str, keyword: str | None = None) -> list[str]:
    """Return fixture log lines for a service.

    `keyword` is a case-insensitive substring filter; without it, every line
    for the service is returned. Unknown services return an empty list.
    """
    logs = json.loads(LOGS_PATH.read_text(encoding="utf-8"))
    lines = logs.get(service, [])
    if keyword is None:
        return lines
    return [line for line in lines if keyword.lower() in line.lower()]
