from collections.abc import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def _normalize_database_url(url: str) -> str:
    """Neon's connection string comes with `?sslmode=require&channel_binding=require`
    by default (the libpq/psycopg convention), but asyncpg's connect() has no
    `sslmode` or `channel_binding` parameter and raises `TypeError: connect() got an
    unexpected keyword argument 'sslmode'` if either is passed through -- SQLAlchemy
    forwards unknown query params straight to the DBAPI as kwargs. Translate to the
    query param asyncpg does understand instead (see docs/05-deployment.md)."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    if sslmode and sslmode != "disable" and "ssl" not in query:
        query["ssl"] = "require"
    return urlunsplit(parts._replace(query=urlencode(query)))


engine = create_async_engine(_normalize_database_url(settings.database_url), pool_pre_ping=True)

async_session_factory = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
