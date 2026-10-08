import json

import httpx
import pytest

from app.agent.errors import ProviderFailure
from app.agent.graph import build_investigator
from app.agent.models import build_chat_models
from app.config import Settings
from app.ollama import OllamaModelRegistry
from tests.scenarios import CHECKOUT


@pytest.fixture
def adapter_settings():
    return Settings(
        postgres_db="unused",
        postgres_user="unused",
        postgres_password="unused",
        ollama_base_url="http://ollama.test:11434",
        llm_request_timeout_seconds=42,
    )


async def test_request_timeout_setting_is_applied_to_model_requests(adapter_settings):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.extensions["timeout"])
        return httpx.Response(500, json={"error": "stub"})

    models = build_chat_models(adapter_settings, transport=httpx.MockTransport(handler))

    with pytest.raises(Exception):
        await models.agent.ainvoke("ping")

    assert seen and seen[0]["read"] == 42


def failing_transport(failure):
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(failure, Exception):
            raise failure
        return httpx.Response(failure, json={"error": "stub failure"})

    return httpx.MockTransport(handler)


@pytest.mark.parametrize(
    "failure",
    [
        500,
        503,
        httpx.ConnectError("connection refused"),
        httpx.ReadTimeout("read timed out"),
    ],
    ids=["http-500", "http-503", "connect-error", "read-timeout"],
)
async def test_ollama_failures_surface_as_provider_failure(adapter_settings, failure):
    models = build_chat_models(adapter_settings, transport=failing_transport(failure))
    investigator = build_investigator(agent_model=models.agent, report_model=models.report)

    with pytest.raises(ProviderFailure):
        await investigator.investigate(CHECKOUT)


async def test_model_registry_lists_installed_model_names(adapter_settings):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"model": "llama3.2:3b", "name": "llama3.2:3b"}]})

    registry = OllamaModelRegistry(adapter_settings, transport=httpx.MockTransport(handler))

    assert await registry.list_models() == ["llama3.2:3b"]


async def test_unreachable_model_registry_raises_connection_error(adapter_settings):
    registry = OllamaModelRegistry(
        adapter_settings, transport=failing_transport(httpx.ConnectError("connection refused"))
    )

    with pytest.raises(ConnectionError):
        await registry.list_models()


async def test_model_registry_server_error_is_reported_as_connection_error(adapter_settings):
    registry = OllamaModelRegistry(adapter_settings, transport=failing_transport(500))

    with pytest.raises(ConnectionError, match="500"):
        await registry.list_models()


async def test_model_registry_pull_follows_streamed_progress(adapter_settings):
    progress = [
        {"status": "pulling manifest"},
        {"status": "pulling dde5aa3fc5ff", "digest": "sha256:dde5", "total": 2000, "completed": 1000},
        {"status": "pulling dde5aa3fc5ff", "digest": "sha256:dde5", "total": 2000, "completed": 2000},
        {"status": "success"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/pull"
        body = "\n".join(json.dumps(line) for line in progress) + "\n"
        return httpx.Response(200, content=body.encode())

    registry = OllamaModelRegistry(adapter_settings, transport=httpx.MockTransport(handler))

    await registry.pull("llama3.2:3b")


async def test_model_registry_pull_reports_progress_in_ten_percent_steps(adapter_settings, capsys):
    total = 4_700_000_000
    progress = [{"status": "pulling manifest"}]
    progress += [
        {"status": "pulling 2bada8a74506", "digest": "sha256:2bada8", "total": total,
         "completed": total * step // 100}
        for step in range(1, 101)
    ]
    progress.append({"status": "success"})

    def handler(request: httpx.Request) -> httpx.Response:
        body = "\n".join(json.dumps(line) for line in progress) + "\n"
        return httpx.Response(200, content=body.encode())

    registry = OllamaModelRegistry(adapter_settings, transport=httpx.MockTransport(handler))

    await registry.pull("qwen2.5:7b")

    progress_lines = [line for line in capsys.readouterr().out.splitlines() if "%" in line]
    assert any("50%" in line for line in progress_lines)
    assert any("100%" in line and "4700 MB" in line for line in progress_lines)
    assert len(progress_lines) <= 11


async def pull_with_progress(adapter_settings, progress) -> None:
    """Pull through a stubbed Ollama that streams `progress`."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = "\n".join(json.dumps(line) for line in progress) + "\n"
        return httpx.Response(200, content=body.encode())

    registry = OllamaModelRegistry(adapter_settings, transport=httpx.MockTransport(handler))
    await registry.pull("qwen2.5:7b")


def layer(digest: str, total: int, completed: int) -> dict:
    return {"status": f"pulling {digest}", "digest": f"sha256:{digest}", "total": total,
            "completed": completed}


async def test_layers_under_one_megabyte_print_no_progress(adapter_settings, capsys):
    await pull_with_progress(adapter_settings, [
        {"status": "pulling manifest"},
        layer("66b9ea09bd5b", 68, 68),
        layer("eb4402837c78", 1482, 1482),
        {"status": "success"},
    ])

    assert "%" not in capsys.readouterr().out


async def test_layer_left_short_of_100_percent_is_completed_once_verifying_starts(
    adapter_settings, capsys
):
    total = 4_683_087_332
    await pull_with_progress(adapter_settings, [
        {"status": "pulling manifest"},
        layer("2bada8a74506", total, total * 95 // 100),
        {"status": "verifying sha256 digest"},
        {"status": "success"},
    ])

    out = capsys.readouterr().out
    assert "100% of 4683 MB (4683 MB)" in out
    assert out.index("100% of 4683 MB") < out.index("verifying sha256 digest")
