"""RAG question answering, citations, history, and retrieval isolation."""

import io
import uuid

import pytest

from app.api.deps import get_llm_factory
from app.main import app

POLICY = (
    "Acme Corporation Refund Policy\n\n"
    "Customers may request a full refund within 30 days of purchase. "
    "Refunds are processed within 5 business days of approval.\n\n"
    "Shipping fees are non-refundable under all circumstances.\n\n"
    "This policy was last updated on 14 March 2024 by the finance team."
).encode()


@pytest.fixture(autouse=True)
def _use_stub_llm(stub_llm):
    app.dependency_overrides[get_llm_factory] = lambda: (lambda: stub_llm)
    yield
    app.dependency_overrides.clear()


def _register(client) -> dict[str, str]:
    email = f"user-{uuid.uuid4().hex[:10]}@example.com"
    token = client.post(
        "/signup", json={"email": email, "password": "Password123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _upload_policy(client, headers, filename="policy.txt", body=POLICY) -> str:
    """Upload and index a document — both phases, so it is ready to query."""
    response = client.post(
        "/upload",
        headers=headers,
        files={"file": (filename, io.BytesIO(body), "text/plain")},
    )
    assert response.status_code == 202, response.text
    document_id = response.json()["id"]

    processed = client.post(f"/documents/{document_id}/process", headers=headers)
    assert processed.status_code == 200, processed.text
    assert processed.json()["status"] == "ready", processed.json().get("error_message")
    return document_id


def _upload_only(client, headers, filename="draft.txt", body=POLICY) -> str:
    """Upload without indexing, leaving the document `pending`."""
    response = client.post(
        "/upload",
        headers=headers,
        files={"file": (filename, io.BytesIO(body), "text/plain")},
    )
    assert response.status_code == 202, response.text
    return response.json()["id"]


def test_ask_returns_grounded_answer_with_sources(client, auth_headers, stub_llm):
    document_id = _upload_policy(client, auth_headers)

    response = client.post(
        "/ask",
        headers=auth_headers,
        json={"question": "What is the refund policy?", "document_id": document_id},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer"] == "Stubbed answer grounded in the provided context [1]."
    assert body["sources"], "expected at least one cited source"
    assert body["sources"][0]["document_name"] == "policy.txt"
    assert 0.0 <= body["sources"][0]["similarity"] <= 1.0

    # The retrieved passage must actually be handed to the model.
    system_prompt, user_prompt = stub_llm.generate_calls[-1]
    assert "ONLY the numbered context passages" in system_prompt
    assert "What is the refund policy?" in user_prompt
    assert "refund" in user_prompt.lower()


def test_ask_without_document_id_searches_all_documents(client, auth_headers):
    _upload_policy(client, auth_headers)

    response = client.post("/ask", headers=auth_headers, json={"question": "Refund window?"})

    assert response.status_code == 200
    assert response.json()["sources"]


def test_ask_before_any_upload_returns_400(client, auth_headers):
    response = client.post("/ask", headers=auth_headers, json={"question": "Anything here?"})

    assert response.status_code == 400
    assert "Upload" in response.json()["detail"]


def test_ask_on_unindexed_document_explains_status(client, auth_headers):
    """A document that hasn't been embedded must not answer from nothing."""
    pending = _upload_only(client, auth_headers)

    response = client.post(
        "/ask",
        headers=auth_headers,
        json={"question": "What does it say?", "document_id": pending},
    )

    assert response.status_code == 400
    assert "not ready" in response.json()["detail"]


def test_ask_ignores_unindexed_documents_when_searching_all(client, auth_headers):
    """An un-embedded document must not make an unscoped question answerable."""
    _upload_only(client, auth_headers)

    response = client.post("/ask", headers=auth_headers, json={"question": "Anything here?"})

    assert response.status_code == 400
    assert "Upload" in response.json()["detail"]


def test_ask_on_another_users_document_returns_404(client):
    alice, bob = _register(client), _register(client)
    document_id = _upload_policy(client, alice, "secret.txt")

    response = client.post(
        "/ask", headers=bob, json={"question": "What is the refund policy?", "document_id": document_id}
    )

    assert response.status_code == 404


def test_retrieval_never_crosses_tenants(client, stub_llm):
    """Bob's unscoped question must not retrieve Alice's chunks."""
    alice, bob = _register(client), _register(client)
    _upload_policy(client, alice, "alice-secret.txt")
    _upload_policy(client, bob, "bob-notes.txt", body=b"Bob's unrelated meeting notes about gardening.")

    response = client.post("/ask", headers=bob, json={"question": "What is the refund policy?"})

    assert response.status_code == 200
    names = {source["document_name"] for source in response.json()["sources"]}
    assert names == {"bob-notes.txt"}
    assert "alice-secret.txt" not in names


def test_ask_validates_question_length(client, auth_headers):
    for question in ["", "ab", "x" * 2001]:
        response = client.post("/ask", headers=auth_headers, json={"question": question})
        assert response.status_code == 422


def test_ask_rejects_unknown_document_id(client, auth_headers):
    response = client.post(
        "/ask", headers=auth_headers, json={"question": "Anything?", "document_id": str(uuid.uuid4())}
    )
    assert response.status_code == 404


def test_history_records_both_sides_of_the_exchange(client, auth_headers):
    document_id = _upload_policy(client, auth_headers)
    client.post(
        "/ask",
        headers=auth_headers,
        json={"question": "What is the refund policy?", "document_id": document_id},
    )

    response = client.get("/history", headers=auth_headers)

    assert response.status_code == 200
    messages = response.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "What is the refund policy?"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["sources"], "assistant message should persist its citations"


def test_history_is_chronological_across_turns(client, auth_headers):
    document_id = _upload_policy(client, auth_headers)
    for question in ["First question here?", "Second question here?"]:
        client.post(
            "/ask", headers=auth_headers, json={"question": question, "document_id": document_id}
        )

    messages = client.get("/history", headers=auth_headers).json()["messages"]

    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[0]["content"] == "First question here?"
    assert messages[2]["content"] == "Second question here?"


def test_history_can_be_filtered_by_document(client, auth_headers):
    first = _upload_policy(client, auth_headers, "one.txt")
    second = _upload_policy(client, auth_headers, "two.txt", body=b"Unrelated gardening notes.")
    client.post("/ask", headers=auth_headers, json={"question": "Refund window?", "document_id": first})
    client.post("/ask", headers=auth_headers, json={"question": "Gardening tips?", "document_id": second})

    filtered = client.get(f"/history?document_id={first}", headers=auth_headers).json()

    assert filtered["total"] == 2
    assert all(m["document_id"] == first for m in filtered["messages"])


def test_history_is_private_to_each_user(client):
    alice, bob = _register(client), _register(client)
    _upload_policy(client, alice)
    client.post("/ask", headers=alice, json={"question": "What is the refund policy?"})

    assert client.get("/history", headers=bob).json()["total"] == 0
    assert client.get("/history", headers=alice).json()["total"] == 2


def test_ask_returns_503_when_llm_is_not_configured(client, auth_headers):
    """Without an API key the endpoint must fail cleanly, not 500."""
    app.dependency_overrides.clear()

    response = client.post("/ask", headers=auth_headers, json={"question": "Anything at all?"})

    assert response.status_code == 503
    assert "detail" in response.json()
