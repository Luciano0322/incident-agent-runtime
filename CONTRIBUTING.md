# Contributing

## Workflow

`main` is protected and always green. All changes go through a pull request.

1. Branch from `main`: `feat/<topic>`, `fix/<topic>`, `docs/<topic>`, or `chore/<topic>`.
2. Work test-first, one slice at a time (red, then green). [docs/TDD-Workflow.md](docs/TDD-Workflow.md) lists the slices and the agreed test seams; tick items as you finish them.
3. Open a PR and fill in the template.
4. Merge with **squash** once CI is green. The branch's red/green commits stay visible in the PR.

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `test:`, `docs:`, `chore:`.

## Tests

| Kind | Command | Runs in CI |
|---|---|---|
| Deterministic (fake model, real PostgreSQL) | `docker compose --profile test run --build --rm tests` | Yes |
| Live model scenario | `docker compose exec api python -m scripts.live_smoke` | No |
| Live model pytest suite | `docker compose --profile test run --build --rm -e OLLAMA_BASE_URL=http://ollama:11434 tests pytest -m llm` | No |

The default test run cannot reach a model: the test container points Ollama at an address that never resolves, and `llm` tests are deselected.

CI never pulls or calls a model. Running one on CPU takes minutes per investigation and gigabytes of download, so live checks run locally. When a change touches prompts, tool descriptions, the Ollama adapter, or the default model, run the live scenario and record every run, pass or fail, in [docs/Verification.md](docs/Verification.md).

## CI gates

| Job | Checks |
|---|---|
| Lockfile | `uv.lock` matches `pyproject.toml` |
| Compose config | Default, test, and CI Compose files are valid |
| Tests | Deterministic tests, including API tests against PostgreSQL |
| Container smoke | Runtime image builds; migrations run and re-run; liveness and the incident API work without a model; `/ready` reports 503 |

The container smoke uses `compose.ci.yaml`, which starts the API without Ollama. It is not a working investigation setup.

## Scope

V1 scope is fixed by [the proposal](docs/incident-agent-runtime-docker-proposal.md). Changes outside it, such as a frontend, RAG, multiple agents, or production deployment, need a design discussion first.
