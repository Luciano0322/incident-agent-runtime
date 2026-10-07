from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health, incidents
from app.config import Settings
from app.db.session import create_sessionmaker


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.sessionmaker = create_sessionmaker(settings)
        yield
        await app.state.sessionmaker.kw["bind"].dispose()

    app = FastAPI(title="incident-agent-runtime", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(incidents.router)
    return app
