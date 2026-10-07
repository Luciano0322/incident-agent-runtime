from fastapi import FastAPI

from app.api import health
from app.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="incident-agent-runtime")
    app.include_router(health.router)
    return app
