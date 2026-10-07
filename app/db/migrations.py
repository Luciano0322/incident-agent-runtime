from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def alembic_config() -> Config:
    return Config(str(ALEMBIC_INI))


def head_revision() -> str | None:
    """The newest migration shipped with this code."""
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


async def applied_revision(session: AsyncSession) -> str | None:
    """The migration the database is currently at."""
    return await session.scalar(text("SELECT version_num FROM alembic_version"))
