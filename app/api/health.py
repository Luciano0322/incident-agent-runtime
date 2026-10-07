from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError

from app.db.migrations import applied_revision, head_revision
from app.ollama import has_model

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", responses={503: {"description": "A dependency is not ready"}})
async def ready(request: Request) -> JSONResponse:
    """Check dependencies without running inference."""
    state = request.app.state
    problems: dict[str, str] = {}

    try:
        async with state.sessionmaker() as session:
            applied = await applied_revision(session)
    except DBAPIError as exc:
        problems["database"] = f"unavailable: {exc.orig.__class__.__name__}"
    else:
        expected = head_revision()
        if applied != expected:
            problems["migrations"] = f"database is at {applied}, code expects {expected}"

    try:
        models = await state.model_registry.list_models()
    except ConnectionError as exc:
        problems["ollama"] = f"unreachable: {exc}"
    else:
        if not has_model(models, state.llm_model):
            problems["model"] = f"{state.llm_model} is not available in Ollama"

    if problems:
        return JSONResponse(
            {"detail": "Not ready", "checks": problems}, status.HTTP_503_SERVICE_UNAVAILABLE
        )
    return JSONResponse({"status": "ready"})
