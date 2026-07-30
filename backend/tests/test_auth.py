"""Signup, login, and protected-route behaviour."""

import uuid


def _email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@example.com"


def test_signup_returns_token_and_user(client):
    email = _email()
    response = client.post("/signup", json={"email": email, "password": "Password123"})

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == email
    assert "password" not in response.text and "hashed" not in response.text


def test_signup_rejects_duplicate_email(client):
    email = _email()
    client.post("/signup", json={"email": email, "password": "Password123"})

    response = client.post("/signup", json={"email": email, "password": "Password123"})

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_signup_normalises_email_case(client):
    email = _email()
    client.post("/signup", json={"email": email.upper(), "password": "Password123"})

    # The lowercase form must collide, and must be able to log in.
    assert client.post(
        "/signup", json={"email": email.lower(), "password": "Password123"}
    ).status_code == 409
    assert client.post(
        "/login", json={"email": email.lower(), "password": "Password123"}
    ).status_code == 200


def test_signup_rejects_weak_passwords(client):
    for password in ["short1", "alllettersnodigits", "12345678", " Password123"]:
        response = client.post("/signup", json={"email": _email(), "password": password})
        assert response.status_code == 422, f"{password!r} should be rejected"


def test_signup_rejects_invalid_email(client):
    response = client.post("/signup", json={"email": "not-an-email", "password": "Password123"})
    assert response.status_code == 422


def test_login_succeeds_with_correct_password(client):
    email = _email()
    client.post("/signup", json={"email": email, "password": "Password123"})

    response = client.post("/login", json={"email": email, "password": "Password123"})

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_rejects_wrong_password(client):
    email = _email()
    client.post("/signup", json={"email": email, "password": "Password123"})

    response = client.post("/login", json={"email": email, "password": "WrongPass123"})

    assert response.status_code == 401


def test_login_hides_whether_email_exists(client):
    """Unknown email and wrong password must be indistinguishable."""
    email = _email()
    client.post("/signup", json={"email": email, "password": "Password123"})

    unknown = client.post("/login", json={"email": _email(), "password": "Password123"})
    wrong = client.post("/login", json={"email": email, "password": "WrongPass123"})

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


def test_me_returns_current_user(client, auth_headers):
    response = client.get("/me", headers=auth_headers)

    assert response.status_code == 200
    assert "@example.com" in response.json()["email"]


def test_protected_routes_require_a_token(client):
    for method, path in [
        ("get", "/me"),
        ("get", "/documents"),
        ("get", "/history"),
        ("post", "/ask"),
        ("post", "/upload"),
    ]:
        response = getattr(client, method)(path)
        assert response.status_code == 401, f"{method.upper()} {path} was not protected"
        assert "detail" in response.json()


def test_malformed_and_tampered_tokens_are_rejected(client, auth_headers):
    valid = auth_headers["Authorization"].removeprefix("Bearer ")
    tampered = valid[:-4] + ("aaaa" if not valid.endswith("aaaa") else "bbbb")

    for token in ["", "garbage", tampered]:
        response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


def test_expired_token_is_rejected(client, auth_headers):
    from datetime import timedelta

    from app.core.security import create_access_token

    user_id = client.get("/me", headers=auth_headers).json()["id"]
    expired = create_access_token(user_id, expires_delta=timedelta(minutes=-5))

    response = client.get("/me", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401


def test_token_signed_with_another_secret_is_rejected(client):
    import jwt

    forged = jwt.encode({"sub": str(uuid.uuid4())}, "attacker-secret", algorithm="HS256")

    response = client.get("/me", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401


def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
