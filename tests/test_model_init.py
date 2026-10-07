from scripts.model_init import initialize_model
from tests.fakes import FakeModelRegistry


async def no_wait(seconds: float) -> None:
    pass


async def test_existing_model_is_not_pulled_again():
    registry = FakeModelRegistry(models=["llama3.2:3b"])

    exit_code = await initialize_model(registry, "llama3.2:3b", sleep=no_wait)

    assert exit_code == 0
    assert registry.pulled == []


async def test_missing_model_is_pulled_and_verified():
    registry = FakeModelRegistry(models=[])

    exit_code = await initialize_model(registry, "llama3.2:3b", sleep=no_wait)

    assert exit_code == 0
    assert registry.pulled == ["llama3.2:3b"]


async def test_pull_that_does_not_install_the_model_fails():
    registry = FakeModelRegistry(models=[], pull_installs=False)

    exit_code = await initialize_model(registry, "llama3.2:3b", sleep=no_wait)

    assert exit_code != 0


async def test_unreachable_ollama_fails_after_bounded_retries_with_a_clear_message(capsys):
    registry = FakeModelRegistry(reachable=False)
    waits = []

    async def record_wait(seconds: float) -> None:
        waits.append(seconds)

    exit_code = await initialize_model(
        registry, "llama3.2:3b", attempts=3, delay=2.0, sleep=record_wait
    )

    assert exit_code != 0
    assert waits == [2.0, 2.0]
    assert "after 3 attempts" in capsys.readouterr().err


async def test_ollama_that_comes_up_within_the_retry_budget_is_used():
    registry = FakeModelRegistry(models=["llama3.2:3b"], unreachable_calls=2)

    exit_code = await initialize_model(registry, "llama3.2:3b", attempts=3, sleep=no_wait)

    assert exit_code == 0
