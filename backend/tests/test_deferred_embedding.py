"""The long-running-server path: phase 2 handed to a background task.

Serverless hosts run embedding inline (the default). Render and Docker set
DEFER_EMBEDDING=true, so that branch needs its own coverage — otherwise a
deploy to Render could ship a code path no test ever ran.
"""

import io

import pytest

from app.api.deps import get_llm_factory
from app.main import app

BODY = (
    "Acme Corporation Refund Policy\n\n"
    "Customers may request a full refund within 30 days of purchase.\n\n"
    "This policy was last updated on 14 March 2024."
).encode()


@pytest.fixture(autouse=True)
def _defer_and_stub(stub_llm, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "defer_embedding", True)
    app.dependency_overrides[get_llm_factory] = lambda: (lambda: stub_llm)
    yield
    app.dependency_overrides.clear()


def _upload(client, headers, filename="policy.txt"):
    response = client.post(
        "/upload",
        headers=headers,
        files={"file": (filename, io.BytesIO(BODY), "text/plain")},
    )
    assert response.status_code == 202, response.text
    return response.json()["id"]


def test_process_returns_processing_then_completes_in_background(client, auth_headers):
    document_id = _upload(client, auth_headers)

    response = client.post(f"/documents/{document_id}/process", headers=auth_headers)

    assert response.status_code == 200
    # The caller is not blocked — it sees the interim state.
    assert response.json()["status"] == "processing"

    # TestClient drains background tasks before returning, so by now it is done.
    detail = client.get(f"/documents/{document_id}", headers=auth_headers).json()
    assert detail["status"] == "ready", detail.get("error_message")
    assert detail["chunk_count"] > 0


def test_deferred_path_makes_the_document_answerable(client, auth_headers):
    document_id = _upload(client, auth_headers)
    client.post(f"/documents/{document_id}/process", headers=auth_headers)

    response = client.post(
        "/ask",
        headers=auth_headers,
        json={"question": "What is the refund policy?", "document_id": document_id},
    )

    assert response.status_code == 200, response.text
    assert response.json()["sources"], "retrieval should find the embedded chunks"
