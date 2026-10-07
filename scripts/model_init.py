"""Make sure the configured Ollama model is available before the API starts.

Run as `python -m scripts.model_init`. Exits non-zero when Ollama cannot be
reached within the retry budget or the model is still missing after a pull.
"""

import asyncio
import sys
from collections.abc import Awaitable, Callable

from app.config import Settings
from app.ollama import ModelRegistry, OllamaModelRegistry, has_model

DEFAULT_ATTEMPTS = 30
DEFAULT_DELAY_SECONDS = 2.0


async def wait_for_models(
    registry: ModelRegistry,
    attempts: int,
    delay: float,
    sleep: Callable[[float], Awaitable[None]],
) -> list[str] | None:
    """List models, retrying while Ollama is unreachable. None if it never answers."""
    for attempt in range(1, attempts + 1):
        try:
            return await registry.list_models()
        except ConnectionError as exc:
            print(f"Ollama not reachable (attempt {attempt}/{attempts}): {exc}")
            if attempt < attempts:
                await sleep(delay)
    return None


async def initialize_model(
    registry: ModelRegistry,
    model: str,
    *,
    attempts: int = DEFAULT_ATTEMPTS,
    delay: float = DEFAULT_DELAY_SECONDS,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> int:
    models = await wait_for_models(registry, attempts, delay, sleep)
    if models is None:
        print(f"Giving up: Ollama was not reachable after {attempts} attempts.", file=sys.stderr)
        return 1
    if has_model(models, model):
        print(f"Model {model} is already available.")
        return 0

    print(f"Pulling model {model}; the first download can take several minutes.")
    try:
        await registry.pull(model)
    except ConnectionError as exc:
        print(f"Could not pull {model}: {exc}", file=sys.stderr)
        return 1
    if has_model(await registry.list_models(), model):
        print(f"Model {model} is available.")
        return 0
    print(f"Pull finished but {model} is still not listed by Ollama.", file=sys.stderr)
    return 1


def main() -> None:
    settings = Settings()
    sys.exit(asyncio.run(initialize_model(OllamaModelRegistry(settings), settings.llm_model)))


if __name__ == "__main__":
    main()
