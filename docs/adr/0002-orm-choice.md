# ADR 0002: SQLAlchemy 2.0 (async) + Alembic instead of Prisma

## Status
Accepted

## Context
Spec named Prisma for the database layer with a FastAPI/Python backend. Prisma's
Python client is community-supported, historically trails the JS/TS client on
features and query ergonomics, and doesn't integrate as cleanly with
async Python patterns used across FastAPI + Celery.

## Decision
Use **SQLAlchemy 2.0** (async engine, `asyncpg` driver) for models/queries and
**Alembic** for migrations. Both are first-class Python, well-documented,
and used by every worker (API, Celery tasks) without a client-generation step.

## Consequences
- One fewer moving part (no `prisma generate` step in CI/deploy).
- Migrations are plain Python/SQL, easy to hand-edit for data backfills.
- Slightly more verbose model definitions than Prisma schema syntax, offset by
  Pydantic v2 models (FastAPI already requires these) generated alongside for
  request/response validation.
