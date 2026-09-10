def _auth_headers(client, email="alice@example.com", password="correct-horse-battery-staple"):
    client.post("/auth/register", json={"email": email, "password": password})
    token = client.post("/auth/login", json={"email": email, "password": password}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


def _create(client, headers, **overrides):
    payload = {"name": "Seelah", "class_name": "champion", "level": 1, **overrides}
    return client.post("/characters", json=payload, headers=headers)


def test_create_character(client) -> None:
    headers = _auth_headers(client)

    response = _create(client, headers, ancestry="human", hp_max=20, hp_current=20)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Seelah"
    assert body["ancestry"] == "human"
    assert body["hp_max"] == 20
    assert body["sheet_data"] == {}
    assert "id" in body


def test_create_character_requires_auth(client) -> None:
    response = client.post("/characters", json={"name": "Seelah"})

    assert response.status_code == 401


def test_list_characters_returns_only_own(client) -> None:
    alice_headers = _auth_headers(client, email="alice@example.com")
    bob_headers = _auth_headers(client, email="bob@example.com")
    _create(client, alice_headers, name="Alice's PC")
    _create(client, bob_headers, name="Bob's PC")

    response = client.get("/characters", headers=alice_headers)

    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert names == ["Alice's PC"]


def test_get_character_by_owner(client) -> None:
    headers = _auth_headers(client)
    character_id = _create(client, headers).json()["id"]

    response = client.get(f"/characters/{character_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == character_id


def test_get_character_not_owned_is_404(client) -> None:
    alice_headers = _auth_headers(client, email="alice@example.com")
    bob_headers = _auth_headers(client, email="bob@example.com")
    character_id = _create(client, alice_headers).json()["id"]

    response = client.get(f"/characters/{character_id}", headers=bob_headers)

    assert response.status_code == 404


def test_get_nonexistent_character_is_404(client) -> None:
    headers = _auth_headers(client)

    response = client.get("/characters/999", headers=headers)

    assert response.status_code == 404


def test_update_character_partial(client) -> None:
    headers = _auth_headers(client)
    character_id = _create(client, headers, hp_max=20, hp_current=20).json()["id"]

    response = client.patch(
        f"/characters/{character_id}", json={"hp_current": 15}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["hp_current"] == 15
    assert body["hp_max"] == 20
    assert body["name"] == "Seelah"


def test_update_character_not_owned_is_404(client) -> None:
    alice_headers = _auth_headers(client, email="alice@example.com")
    bob_headers = _auth_headers(client, email="bob@example.com")
    character_id = _create(client, alice_headers).json()["id"]

    response = client.patch(
        f"/characters/{character_id}", json={"hp_current": 1}, headers=bob_headers
    )

    assert response.status_code == 404


def test_delete_character(client) -> None:
    headers = _auth_headers(client)
    character_id = _create(client, headers).json()["id"]

    response = client.delete(f"/characters/{character_id}", headers=headers)
    assert response.status_code == 204

    get_response = client.get(f"/characters/{character_id}", headers=headers)
    assert get_response.status_code == 404


def test_delete_character_not_owned_is_404(client) -> None:
    alice_headers = _auth_headers(client, email="alice@example.com")
    bob_headers = _auth_headers(client, email="bob@example.com")
    character_id = _create(client, alice_headers).json()["id"]

    response = client.delete(f"/characters/{character_id}", headers=bob_headers)

    assert response.status_code == 404
