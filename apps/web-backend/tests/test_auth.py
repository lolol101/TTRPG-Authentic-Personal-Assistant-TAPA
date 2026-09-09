def _register(client, email="alice@example.com", password="correct-horse-battery-staple"):
    return client.post("/auth/register", json={"email": email, "password": password})


def test_register_creates_user(client) -> None:
    response = _register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert "id" in body
    assert "password" not in body
    assert "password_hash" not in body


def test_register_rejects_duplicate_email(client) -> None:
    _register(client)

    response = _register(client)

    assert response.status_code == 409


def test_login_with_correct_credentials_returns_token(client) -> None:
    _register(client, password="correct-horse-battery-staple")

    response = client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "correct-horse-battery-staple"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_with_wrong_password_is_rejected(client) -> None:
    _register(client, password="correct-horse-battery-staple")

    response = client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_login_with_unknown_email_is_rejected(client) -> None:
    response = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )

    assert response.status_code == 401


def test_me_returns_current_user_with_valid_token(client) -> None:
    _register(client, password="correct-horse-battery-staple")
    login_response = client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "correct-horse-battery-staple"},
    )
    token = login_response.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_me_without_token_is_rejected(client) -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_me_with_garbage_token_is_rejected(client) -> None:
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401
