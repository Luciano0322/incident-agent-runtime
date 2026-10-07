from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from app.tools.logs import query_logs


class QueryLogsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str = Field(description="Service name, for example checkout or payment.")
    keyword: str | None = Field(
        default=None,
        description=(
            "Optional case-insensitive substring of the log line text, for example"
            " 'timeout'. Not a time filter. Omit it to get every line for the service."
        ),
    )


def default_tools() -> dict[str, StructuredTool]:
    tool = StructuredTool.from_function(
        func=query_logs,
        name="query_logs",
        description="Return log lines for a service, optionally filtered by keyword.",
        args_schema=QueryLogsArgs,
    )
    return {tool.name: tool}
