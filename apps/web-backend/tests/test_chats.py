from sqlmodel import select

from app.core import chat_store
from app.models.chat import Chat
from app.models.user import User


def _auth_headers(client, email="alice@example.com", password="correct-horse-battery-staple"):
    client.post("/auth/register", json={"email": email, "password": password})
    token = client.post("/auth/login", json={"email": email, "password": password}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


def _create_character(client, headers, name="Рэм Байер"):
    return client.post("/characters", json={"name": name}, headers=headers).json()


def _user(session, email="alice@example.com") -> User:
    return session.exec(select(User).where(User.email == email)).one()


def _stored_chat(session, chat_id: int) -> Chat:
    return session.get(Chat, chat_id)


def test_chats_require_authentication(client) -> None:
    assert client.get("/chats").status_code == 401
    assert client.post("/chats", json={}).status_code == 401


def test_a_new_chat_starts_empty_and_shows_up_in_the_list(client) -> None:
    headers = _auth_headers(client)

    created = client.post("/chats", json={"title": "Про захваты"}, headers=headers)

    assert created.status_code == 201
    assert created.json()["message_count"] == 0

    listed = client.get("/chats", headers=headers).json()
    assert [chat["title"] for chat in listed] == ["Про захваты"]


def test_chats_are_listed_most_recently_used_first(client) -> None:
    headers = _auth_headers(client)
    first = client.post("/chats", json={"title": "старый"}, headers=headers).json()
    client.post("/chats", json={"title": "новый"}, headers=headers)

    client.patch(f"/chats/{first['id']}", json={"title": "снова старый"}, headers=headers)

    listed = client.get("/chats", headers=headers).json()
    assert listed[0]["title"] == "снова старый"


def test_one_user_cannot_reach_another_users_chat(client) -> None:
    alice = _auth_headers(client)
    chat = client.post("/chats", json={"title": "личное"}, headers=alice).json()
    bob = _auth_headers(client, email="bob@example.com")

    assert client.get("/chats", headers=bob).json() == []
    assert client.get(f"/chats/{chat['id']}", headers=bob).status_code == 404
    assert client.patch(f"/chats/{chat['id']}", json={"title": "x"}, headers=bob).status_code == 404
    assert client.delete(f"/chats/{chat['id']}", headers=bob).status_code == 404
    assert client.get(f"/chats/{chat['id']}/messages", headers=bob).status_code == 404


def test_a_chat_can_only_point_at_a_character_its_owner_has(client) -> None:
    alice = _auth_headers(client)
    character = _create_character(client, alice)
    bob = _auth_headers(client, email="bob@example.com")

    response = client.post("/chats", json={"character_id": character["id"]}, headers=bob)

    assert response.status_code == 404


def test_the_remembered_character_can_be_changed_and_cleared(client) -> None:
    headers = _auth_headers(client)
    character = _create_character(client, headers)
    chat = client.post("/chats", json={"character_id": character["id"]}, headers=headers).json()

    cleared = client.patch(f"/chats/{chat['id']}", json={"character_id": None}, headers=headers)

    assert cleared.json()["character_id"] is None


def test_deleting_a_character_leaves_its_chats_standing(client) -> None:
    """The rules discussion in them is still worth reading afterwards."""
    headers = _auth_headers(client)
    character = _create_character(client, headers)
    chat = client.post("/chats", json={"character_id": character["id"]}, headers=headers).json()

    assert client.delete(f"/characters/{character['id']}", headers=headers).status_code == 204

    remaining = client.get(f"/chats/{chat['id']}", headers=headers).json()
    assert remaining["character_id"] is None


def test_deleting_a_chat_takes_its_messages_with_it(client, session_factory) -> None:
    headers = _auth_headers(client)
    chat = client.post("/chats", json={}, headers=headers).json()
    with session_factory() as session:
        chat_store.add_message(_stored_chat(session, chat["id"]), session, role="user", text="в")

    assert client.delete(f"/chats/{chat['id']}", headers=headers).status_code == 204

    with session_factory() as session:
        assert chat_store.list_messages(chat["id"], session) == []


def test_the_chat_limit_is_reported_rather_than_silently_hit(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    monkeypatch.setattr(chat_store.settings, "max_chats_per_user", 1)
    client.post("/chats", json={}, headers=headers)

    refused = client.post("/chats", json={}, headers=headers)

    assert refused.status_code == 409
    assert "предел" in refused.json()["detail"]


def test_the_chat_limit_counts_only_this_users_chats(client, monkeypatch) -> None:
    monkeypatch.setattr(chat_store.settings, "max_chats_per_user", 1)
    alice = _auth_headers(client)
    client.post("/chats", json={}, headers=alice)
    bob = _auth_headers(client, email="bob@example.com")

    assert client.post("/chats", json={}, headers=bob).status_code == 201


def test_applying_the_changes_is_remembered_across_a_reload(client, session_factory) -> None:
    """Otherwise a reload offers to apply the same damage a second time."""
    headers = _auth_headers(client)
    chat = client.post("/chats", json={}, headers=headers).json()
    with session_factory() as session:
        message_id = chat_store.add_message(
            _stored_chat(session, chat["id"]), session, role="assistant", text="ответ"
        ).id

    response = client.patch(
        f"/chats/{chat['id']}/messages/{message_id}", json={"applied": True}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["applied"] is True
    assert client.get(f"/chats/{chat['id']}/messages", headers=headers).json()[0]["applied"] is True


def test_a_message_from_another_chat_is_not_reachable(client, session_factory) -> None:
    headers = _auth_headers(client)
    first = client.post("/chats", json={}, headers=headers).json()
    second = client.post("/chats", json={}, headers=headers).json()
    with session_factory() as session:
        message_id = chat_store.add_message(
            _stored_chat(session, first["id"]), session, role="user", text="вопрос"
        ).id

    response = client.patch(
        f"/chats/{second['id']}/messages/{message_id}", json={"applied": True}, headers=headers
    )

    assert response.status_code == 404


def test_an_untitled_chat_is_named_after_its_first_question(client, session_factory) -> None:
    headers = _auth_headers(client)
    chat = client.post("/chats", json={}, headers=headers).json()
    assert chat["title"] == ""

    with session_factory() as session:
        chat_store.add_message(
            _stored_chat(session, chat["id"]), session, role="user", text="Как работает Захват?"
        )

    assert client.get(f"/chats/{chat['id']}", headers=headers).json()["title"] == (
        "Как работает Захват?"
    )


def test_a_long_first_question_is_cut_to_a_readable_title() -> None:
    title = chat_store.title_from("Что делает это действие " * 10)

    assert len(title) <= 60
    assert title.endswith("…")


def test_a_title_the_user_chose_is_not_overwritten(client, session_factory) -> None:
    headers = _auth_headers(client)
    chat = client.post("/chats", json={"title": "Мой чат"}, headers=headers).json()

    with session_factory() as session:
        chat_store.add_message(
            _stored_chat(session, chat["id"]), session, role="user", text="вопрос"
        )

    assert client.get(f"/chats/{chat['id']}", headers=headers).json()["title"] == "Мой чат"


def test_history_carries_the_text_but_not_the_sources(client, session_factory) -> None:
    """Re-sending retrieved rule text every turn would fill the window with
    the same passages over and over."""
    headers = _auth_headers(client)
    chat = client.post("/chats", json={}, headers=headers).json()

    with session_factory() as session:
        chat_store.add_message(
            _stored_chat(session, chat["id"]),
            session,
            role="assistant",
            text="Захват обездвиживает цель.",
            sources=[{"title": "Захват", "url": "https://pf2.ru/actions/grapple"}],
        )
        history = chat_store.history_for(chat["id"], session)

    assert history == [{"role": "assistant", "text": "Захват обездвиживает цель."}]
