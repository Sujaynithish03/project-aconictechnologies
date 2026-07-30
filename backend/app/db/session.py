"""SQLAlchemy engine and session lifecycle."""

import os
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings

# On serverless the process is frozen between invocations, so a pooled
# connection is almost always dead by the next request and each concurrent
# instance would hold its own pool. NullPool defers pooling to the database's
# own pooler (Neon's -pooler endpoint) instead.
_is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

_engine_options: dict[str, object] = {"echo": settings.debug}
if _is_serverless:
    _engine_options["poolclass"] = NullPool
else:
    _engine_options.update(
        pool_pre_ping=True,  # Idle connections get dropped; probe before use.
        pool_recycle=300,
    )

engine = create_engine(settings.database_url, **_engine_options)  # type: ignore[arg-type]

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Ensure the pgvector extension, all tables, and added columns exist."""
    from app.db.base import Base  # noqa: PLC0415  (imported here to register models)

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)

    # create_all() creates missing tables but never alters existing ones, so
    # columns added after a database was first provisioned need explicit DDL.
    # These statements are idempotent. This is the documented cost of skipping
    # Alembic — the first schema change beyond this should introduce it.
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS raw_text TEXT")
        )
