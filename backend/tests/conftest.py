"""Test fixtures.

Runs against a dedicated ``knowledge_base_test`` database created on the fly, so
tests never touch development data. The environment is configured before any
``app`` module is imported, because settings and the engine are built at import
time.
"""

import os
import uuid
from collections.abc import Iterator

import pytest

ADMIN_URL = os.environ.get(
    "TEST_ADMIN_DATABASE_URL", "postgresql+psycopg://kb:kb@localhost:5432/postgres"
)
TEST_DB_NAME = "knowledge_base_test"
TEST_DB_URL = ADMIN_URL.rsplit("/", 1)[0] + f"/{TEST_DB_NAME}"

os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["JWT_SECRET"] = "test-secret-not-used-in-production"
os.environ["GEMINI_API_KEY"] = ""  # Force use of the stub provider.
os.environ["EMBEDDING_DIMENSIONS"] = "8"  # Tiny vectors keep the stub readable.
os.environ["CORS_ORIGINS"] = "http://localhost:5173"


def _create_test_database() -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": TEST_DB_NAME},
            ).scalar()
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    finally:
        engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    try:
        _create_test_database()
    except Exception as error:  # pragma: no cover
        pytest.skip(f"Postgres unavailable, skipping DB tests: {error}")

    from app.db.base import Base
    from app.db.session import engine, init_db

    init_db()
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    """Truncate between tests so each one starts from a known state."""
    from sqlalchemy import text

    from app.db.session import engine

    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE messages, document_chunks, documents, users "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


class StubLLMProvider:
    """Deterministic stand-in for Gemini — no network, no API key, no cost.

    Embeddings are derived from character histograms, so texts sharing words
    land near each other and similarity search behaves realistically.
    """

    dimensions = 8

    def __init__(self) -> None:
        self.generate_calls: list[tuple[str, str]] = []

    @property
    def embedding_dimensions(self) -> int:
        return self.dimensions

    def _vector(self, text: str) -> list[float]:
        buckets = [0.0] * self.dimensions
        for token in text.lower().split():
            # Deterministic bucket: Python's str hash is salted per process.
            buckets[sum(token.encode()) % self.dimensions] += 1.0
        magnitude = sum(value * value for value in buckets) ** 0.5
        if magnitude == 0:
            return [1.0] + [0.0] * (self.dimensions - 1)
        return [value / magnitude for value in buckets]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.generate_calls.append((system_prompt, user_prompt))
        return "Stubbed answer grounded in the provided context [1]."


@pytest.fixture
def stub_llm() -> StubLLMProvider:
    return StubLLMProvider()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client) -> dict[str, str]:
    """Register a unique user and return its Authorization header."""
    email = f"user-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/signup", json={"email": email, "password": "Password123"}
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
