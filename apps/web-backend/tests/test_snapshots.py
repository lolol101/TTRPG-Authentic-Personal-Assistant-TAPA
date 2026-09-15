from app.api import snapshots


def _auth_headers(client, email="alice@example.com", password="correct-horse-battery-staple"):
    client.post("/auth/register", json={"email": email, "password": password})
    token = client.post("/auth/login", json={"email": email, "password": password}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


def _character(client, headers, **fields) -> dict:
    payload = {"name": "Рэм", "hp_max": 40, "hp_current": 40, **fields}
    return client.post("/characters", json=payload, headers=headers).json()


def test_snapshots_require_authentication(client) -> None:
    assert client.get("/characters/1/snapshots").status_code == 401


def test_a_saved_sheet_can_be_brought_back(client) -> None:
    headers = _auth_headers(client)
    character = _character(client, headers)
    saved = client.post(
        f"/characters/{character['id']}/snapshots", json={"name": "до боя"}, headers=headers
    ).json()

    client.patch(
        f"/characters/{character['id']}", json={"hp_current": 3, "level": 9}, headers=headers
    )

    client.post(f"/characters/{character['id']}/snapshots/{saved['id']}/restore", headers=headers)

    restored = client.get(f"/characters/{character['id']}", headers=headers).json()
    assert restored["hp_current"] == 40
    assert restored["level"] == character["level"]


def test_the_sheet_document_comes_back_too(client) -> None:
    """Conditions and cards live in sheet_data; a restore that skipped it
    would look like it worked and quietly lose most of the sheet."""
    headers = _auth_headers(client)
    character = _character(client, headers)
    client.patch(
        f"/characters/{character['id']}",
        json={"sheet_data": {"hero_points": 3, "conditions": {"frightened": 2}}},
        headers=headers,
    )
    saved = client.post(f"/characters/{character['id']}/snapshots", json={}, headers=headers).json()

    client.patch(
        f"/characters/{character['id']}", json={"sheet_data": {"hero_points": 0}}, headers=headers
    )
    client.post(f"/characters/{character['id']}/snapshots/{saved['id']}/restore", headers=headers)

    restored = client.get(f"/characters/{character['id']}", headers=headers).json()
    assert restored["sheet_data"] == {"hero_points": 3, "conditions": {"frightened": 2}}


def test_an_unnamed_save_is_labelled_with_its_time(client) -> None:
    headers = _auth_headers(client)
    character = _character(client, headers)

    saved = client.post(f"/characters/{character['id']}/snapshots", json={}, headers=headers).json()

    assert saved["name"].strip()


def test_saves_are_listed_newest_first(client) -> None:
    headers = _auth_headers(client)
    character = _character(client, headers)
    for name in ("первое", "второе"):
        client.post(
            f"/characters/{character['id']}/snapshots", json={"name": name}, headers=headers
        )

    listed = client.get(f"/characters/{character['id']}/snapshots", headers=headers).json()

    assert [item["name"] for item in listed] == ["второе", "первое"]


def test_one_player_cannot_reach_another_players_saves(client) -> None:
    alice = _auth_headers(client)
    character = _character(client, alice)
    saved = client.post(f"/characters/{character['id']}/snapshots", json={}, headers=alice).json()
    bob = _auth_headers(client, email="bob@example.com")

    assert client.get(f"/characters/{character['id']}/snapshots", headers=bob).status_code == 404
    assert (
        client.post(
            f"/characters/{character['id']}/snapshots/{saved['id']}/restore", headers=bob
        ).status_code
        == 404
    )


def test_a_save_from_another_character_cannot_be_restored(client) -> None:
    """Otherwise one character's sheet could be written over another's."""
    headers = _auth_headers(client)
    mine = _character(client, headers)
    other = _character(client, headers, name="Сила")
    saved = client.post(f"/characters/{other['id']}/snapshots", json={}, headers=headers).json()

    response = client.post(
        f"/characters/{mine['id']}/snapshots/{saved['id']}/restore", headers=headers
    )

    assert response.status_code == 404


def test_restoring_does_not_move_the_sheet_to_another_owner(client) -> None:
    headers = _auth_headers(client)
    character = _character(client, headers)
    saved = client.post(f"/characters/{character['id']}/snapshots", json={}, headers=headers).json()

    client.post(f"/characters/{character['id']}/snapshots/{saved['id']}/restore", headers=headers)

    restored = client.get(f"/characters/{character['id']}", headers=headers).json()
    assert restored["owner_id"] == character["owner_id"]
    assert restored["id"] == character["id"]


def test_the_save_limit_is_reported_rather_than_silently_hit(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    character = _character(client, headers)
    monkeypatch.setattr(snapshots.settings, "max_snapshots_per_character", 1)
    client.post(f"/characters/{character['id']}/snapshots", json={}, headers=headers)

    refused = client.post(f"/characters/{character['id']}/snapshots", json={}, headers=headers)

    assert refused.status_code == 409
    assert "предел" in refused.json()["detail"]


def test_a_deleted_save_is_gone(client) -> None:
    headers = _auth_headers(client)
    character = _character(client, headers)
    saved = client.post(f"/characters/{character['id']}/snapshots", json={}, headers=headers).json()

    assert (
        client.delete(
            f"/characters/{character['id']}/snapshots/{saved['id']}", headers=headers
        ).status_code
        == 204
    )
    assert client.get(f"/characters/{character['id']}/snapshots", headers=headers).json() == []


def test_deleting_a_character_takes_its_saves_with_it(client, session_factory) -> None:
    from sqlmodel import select

    from app.models.snapshot import CharacterSnapshot

    headers = _auth_headers(client)
    character = _character(client, headers)
    client.post(f"/characters/{character['id']}/snapshots", json={}, headers=headers)

    client.delete(f"/characters/{character['id']}", headers=headers)

    with session_factory() as session:
        remaining = list(
            session.exec(
                select(CharacterSnapshot).where(CharacterSnapshot.character_id == character["id"])
            )
        )
    assert remaining == []


def test_a_save_carries_no_identity_to_write_back(client) -> None:
    """capture() is what a restore writes; id or owner_id in there would let
    a restore quietly reassign the sheet."""
    assert "id" not in snapshots.SAVED_FIELDS
    assert "owner_id" not in snapshots.SAVED_FIELDS
    assert "ruleset" not in snapshots.SAVED_FIELDS
