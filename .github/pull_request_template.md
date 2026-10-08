## What and why

<!-- What does this change and why? Link the TDD-Workflow items it covers (docs/TDD-Workflow.md). -->

## How it was verified

- [ ] Red seen before green for each new behavior (or noted why a test passed immediately)
- [ ] `docker compose --profile test run --build --rm tests` passes locally
- [ ] CI is green

## Model-facing changes

<!-- Prompts, tool descriptions, the Ollama adapter, or the default model. CI never runs a model. -->

- [ ] Not applicable
- [ ] Ran `docker compose exec api python -m scripts.live_smoke` locally and recorded every run, pass or fail, in `docs/Verification.md`
