"""Create the pgvector extension and all tables against DATABASE_URL.

Run once per environment when AUTO_INIT_DB is disabled (serverless), so cold
starts don't re-run schema creation on every invocation.

    python scripts/init_db.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import engine, init_db  # noqa: E402


def main() -> int:
    target = settings.database_url.rsplit("@", 1)[-1]  # never print credentials
    print(f"Initialising schema on ...@{target}")

    init_db()

    with engine.connect() as connection:
        tables = [
            row[0]
            for row in connection.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' ORDER BY 1"
                )
            )
        ]
        has_vector = connection.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
        dimensions = connection.execute(
            text(
                "SELECT atttypmod FROM pg_attribute a "
                "JOIN pg_class r ON r.oid = a.attrelid "
                "WHERE r.relname = 'document_chunks' AND attname = 'embedding'"
            )
        ).scalar()

    print(f"  pgvector installed : {bool(has_vector)}")
    print(f"  tables             : {tables}")
    print(f"  embedding dims     : {dimensions}")

    expected = {"users", "documents", "document_chunks", "messages"}
    missing = expected - set(tables)
    if missing or not has_vector:
        print(f"FAILED — missing tables {missing or 'none'}, vector={bool(has_vector)}")
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
