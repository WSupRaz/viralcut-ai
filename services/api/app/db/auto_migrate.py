"""Schema self-healing for PaaS deploys.

The API must never serve against a schema its code doesn't understand, so
every boot runs `alembic upgrade head` (entrypoint.sh, and again at app
startup as a fallback for PaaS configs that override the Docker CMD).

The complication is databases created *outside* Alembic: the original
codebase bootstrapped via `create_all`, so production DBs commonly have no
`alembic_version` rows at all. `upgrade head` from an empty version table
fails on the base migration's `create_table` calls (the tables already
exist), which used to leave deploys "successful" while every new-column
query 500'd.

`run_migrations()` heals that exact state: if `upgrade head` fails but the
base schema is present, it stamps the base revision (metadata-only -- just
writes the version row, touches no DDL) and re-runs the upgrade. The
remaining migrations are all idempotent (`IF NOT EXISTS` / `ON CONFLICT`),
so this converges, and the same idempotency makes concurrent replica boots
safe.
"""

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.db.session import _normalize_database_url

# Revision that created the base schema. If those tables exist but alembic
# has no version for them, we can safely stamp here and let upgrade apply
# only the (idempotent) seed + column migrations.
BASE_REVISION = "49822dc945f9"

# Tables created by the base migration. All must exist for the heal path.
CORE_TABLES = (
    "users",
    "projects",
    "source_videos",
    "jobs",
    "styles",
    "metadata",
)


def _cfg() -> AlembicConfig:
    api_dir = Path(__file__).resolve().parents[2]
    cfg = AlembicConfig(str(api_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(api_dir / "app/db/migrations"))
    return cfg


async def _base_schema_exists() -> bool:
    engine = create_async_engine(_normalize_database_url(settings.database_url))
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = ANY(:tables)"
                ),
                {"tables": list(CORE_TABLES)},
            )
            found = {row[0] for row in rows}
        return found.issuperset(CORE_TABLES)
    finally:
        await engine.dispose()


def run_migrations() -> None:
    """Bring the schema to head; heal DBs created outside Alembic."""
    cfg = _cfg()
    try:
        command.upgrade(cfg, "head")
        return
    except Exception as exc:  # noqa: BLE001 -- first attempt failed; try heal
        first_error = exc

    try:
        if not asyncio.run(_base_schema_exists()):
            raise RuntimeError("base schema tables are missing") from first_error
        print(
            "[auto-migrate] base schema present but alembic is not at head -- "
            "stamping base revision and re-running upgrade (healing a DB "
            "created outside Alembic)",
            flush=True,
        )
        command.stamp(cfg, BASE_REVISION)
        command.upgrade(cfg, "head")
        print("[auto-migrate] healed: schema is now at head.", flush=True)
    except Exception as heal_error:  # noqa: BLE001
        raise RuntimeError(
            f"migration failed: {first_error}\n"
            f"heal attempt failed: {heal_error}"
        ) from first_error


def main() -> None:
    try:
        run_migrations()
        print("[auto-migrate] OK", flush=True)
    except Exception as exc:  # noqa: BLE001 -- boot must not crash (see entrypoint)
        print(f"[auto-migrate] FAILED (continuing): {exc}", flush=True)


if __name__ == "__main__":
    main()
