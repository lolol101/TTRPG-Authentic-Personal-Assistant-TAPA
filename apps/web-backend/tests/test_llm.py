import httpx

from app.api import llm


def _auth_headers(client, email="alice@example.com", password="correct-horse-battery-staple"):
    client.post("/auth/register", json={"email": email, "password": password})
    token = client.post("/auth/login", json={"email": email, "password": password}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_ping_returns_llm_service_health(client, monkeypatch) -> None:
    monkeypatch.setattr(
        llm.httpx,
        "get",
        lambda url, timeout: _FakeResponse({"status": "ok", "service": "llm-service"}),
    )

    response = client.get("/llm/ping")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "llm-service"}


def test_ping_returns_502_when_llm_service_unreachable(client, monkeypatch) -> None:
    def _raise(url, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(llm.httpx, "get", _raise)

    response = client.get("/llm/ping")

    assert response.status_code == 502


class _FakeAskResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> dict:
        return self._payload


def _stub_ask(monkeypatch, captured: dict | None = None):
    def _fake_post(url, json, timeout):
        if captured is not None:
            captured["url"] = url
            captured["json"] = json
        source = {"title": "Удар", "url": "https://pf2.ru/actions/strike", "source_book": ""}
        return _FakeAskResponse(200, {"answer": "Удар наносит урон.", "sources": [source]})

    monkeypatch.setattr(llm.httpx, "post", _fake_post)


def test_ask_requires_authentication(client) -> None:
    response = client.post("/llm/ask", json={"question": "Что делает Удар?"})

    assert response.status_code == 401


def test_ask_proxies_question_and_returns_answer(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    captured: dict = {}
    _stub_ask(monkeypatch, captured)

    response = client.post("/llm/ask", json={"question": "Что делает Удар?"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["answer"] == "Удар наносит урон."
    assert captured["url"].endswith("/ask")
    assert captured["json"] == {
        "question": "Что делает Удар?",
        "k": None,
        "ruleset": None,
        "character_context": None,
        "allow_sheet_edits": False,
        "history": [],
    }


def test_a_chosen_character_decides_which_rules_are_searched(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    character_id = client.post(
        "/characters", json={"name": "Рэм", "ruleset": "dnd5e"}, headers=headers
    ).json()["id"]
    captured: dict = {}
    _stub_ask(monkeypatch, captured)

    client.post(
        "/llm/ask",
        json={"question": "вопрос", "character_id": character_id, "ruleset": "pf2e"},
        headers=headers,
    )

    # The sheet's own system wins over whatever the request asked for.
    assert captured["json"]["ruleset"] == "dnd5e"


def test_ask_sends_the_sheet_when_a_character_is_named(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    character_id = client.post(
        "/characters",
        json={"name": "Рэм Байер", "level": 5, "str_mod": 4},
        headers=headers,
    ).json()["id"]
    captured: dict = {}
    _stub_ask(monkeypatch, captured)

    response = client.post(
        "/llm/ask",
        json={"question": "Хватит ли мне Атлетики?", "character_id": character_id},
        headers=headers,
    )

    assert response.status_code == 200
    context = captured["json"]["character_context"]
    assert "Рэм Байер" in context
    assert "Атлетика (СИЛ): +4" in context
    # character_id is resolved here and must not leak onward to llm-service.
    assert "character_id" not in captured["json"]


def test_ask_refuses_a_character_owned_by_someone_else(client, monkeypatch) -> None:
    alice_headers = _auth_headers(client, email="alice@example.com")
    bob_headers = _auth_headers(client, email="bob@example.com")
    character_id = client.post(
        "/characters", json={"name": "Alice's PC"}, headers=alice_headers
    ).json()["id"]
    _stub_ask(monkeypatch)

    response = client.post(
        "/llm/ask",
        json={"question": "вопрос", "character_id": character_id},
        headers=bob_headers,
    )

    assert response.status_code == 404


def test_ask_returns_404_for_an_unknown_character(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    _stub_ask(monkeypatch)

    response = client.post(
        "/llm/ask", json={"question": "вопрос", "character_id": 999}, headers=headers
    )

    assert response.status_code == 404


def test_ask_forwards_llm_service_error_status(client, monkeypatch) -> None:
    headers = _auth_headers(client)

    def _fake_post(url, json, timeout):
        return _FakeAskResponse(503, {"detail": "not configured"})

    monkeypatch.setattr(llm.httpx, "post", _fake_post)

    response = client.post("/llm/ask", json={"question": "вопрос"}, headers=headers)

    assert response.status_code == 503


def test_ask_returns_502_when_llm_service_unreachable(client, monkeypatch) -> None:
    headers = _auth_headers(client)

    def _raise(url, json, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(llm.httpx, "post", _raise)

    response = client.post("/llm/ask", json={"question": "вопрос"}, headers=headers)

    assert response.status_code == 502


def _stub_ask_with_proposals(monkeypatch, proposals: list[dict], captured: dict | None = None):
    def _fake_post(url, json, timeout):
        if captured is not None:
            captured["json"] = json
        return _FakeAskResponse(
            200, {"answer": "Готово.", "sources": [], "proposed_changes": proposals}
        )

    monkeypatch.setattr(llm.httpx, "post", _fake_post)


def test_ask_offers_sheet_edits_only_with_a_character(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    captured: dict = {}
    _stub_ask_with_proposals(monkeypatch, [], captured)

    client.post("/llm/ask", json={"question": "вопрос"}, headers=headers)

    assert captured["json"]["allow_sheet_edits"] is False


def test_ask_returns_validated_proposals_without_applying_them(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    character_id = client.post(
        "/characters", json={"name": "Рэм", "level": 5, "hp_current": 60}, headers=headers
    ).json()["id"]
    _stub_ask_with_proposals(
        monkeypatch, [{"path": "hp_current", "value": 42, "reason": "получил урон"}]
    )

    response = client.post(
        "/llm/ask",
        json={"question": "я получил 18 урона", "character_id": character_id},
        headers=headers,
    )

    assert response.status_code == 200
    changes = response.json()["proposed_changes"]
    assert changes == [
        {
            "path": "hp_current",
            "value": 42,
            "reason": "получил урон",
            "label": "Текущие ПЗ",
            "before": 60,
            # Nothing vouches for the arithmetic behind 42: the proposal
            # carried no basis or delta.
            "verified": False,
            "section": "Основное",
        }
    ]

    # Nothing may be written until the player confirms.
    stored = client.get(f"/characters/{character_id}", headers=headers).json()
    assert stored["hp_current"] == 60


def test_ask_drops_proposals_outside_the_whitelist(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    character_id = client.post("/characters", json={"name": "Рэм"}, headers=headers).json()["id"]
    _stub_ask_with_proposals(
        monkeypatch,
        [
            {"path": "hp_current", "value": 10},
            # Ownership stays off limits however much of the sheet is opened.
            {"path": "owner_id", "value": 2},
        ],
    )

    body = client.post(
        "/llm/ask",
        json={"question": "вопрос", "character_id": character_id},
        headers=headers,
    ).json()

    assert [change["path"] for change in body["proposed_changes"]] == ["hp_current"]
    assert len(body["rejected_changes"]) == 1


def test_ask_ignores_proposals_when_no_character_is_selected(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    _stub_ask_with_proposals(monkeypatch, [{"path": "hp_current", "value": 1}])

    body = client.post("/llm/ask", json={"question": "вопрос"}, headers=headers).json()

    assert body["proposed_changes"] == []


def _stub_ask_sequence(monkeypatch, responses: list[dict]):
    """Each call to llm-service returns the next stubbed response in order."""
    calls: list[dict] = []

    def _fake_post(url, json, timeout):
        calls.append(json)
        payload = responses[min(len(calls) - 1, len(responses) - 1)]
        return _FakeAskResponse(200, payload)

    monkeypatch.setattr(llm.httpx, "post", _fake_post)
    return calls


def test_a_rejected_path_gets_one_retry_with_what_the_checker_found(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    character_id = client.post("/characters", json={"name": "Рэм"}, headers=headers).json()["id"]
    calls = _stub_ask_sequence(
        monkeypatch,
        [
            {
                "answer": "Собрал.",
                "sources": [],
                "proposed_changes": [
                    {"path": "sheet_data.made_up_field", "value": "что-то"},
                ],
            },
            {
                "answer": "",
                "sources": [],
                # The corrected call proposes a real column instead.
                "proposed_changes": [{"path": "ancestry", "value": "Человек"}],
            },
        ],
    )

    body = client.post(
        "/llm/ask",
        json={"question": "Собери персонажа", "character_id": character_id},
        headers=headers,
    ).json()

    assert len(calls) == 2
    assert body["proposed_changes"] == [
        {
            "path": "ancestry",
            "value": "Человек",
            "reason": "",
            "label": "Происхождение",
            "before": "",
            "verified": False,
            "section": "Личность",
        }
    ]
    assert body["rejected_changes"] == []

    # The retry is told what happened, in words the model can act on.
    retry_request = calls[1]
    assert "sheet_data.made_up_field" in retry_request["retry_feedback"]
    assert "недоступен" in retry_request["retry_feedback"]
    assert retry_request["history"][-2] == {"role": "user", "text": "Собери персонажа"}
    assert retry_request["history"][-1] == {"role": "assistant", "text": "Собрал."}


def test_no_rejection_means_no_retry_call_at_all(client, monkeypatch) -> None:
    """The whole point: when the checker has nothing to report, there is
    nothing for the model to read, so no second call is made."""
    headers = _auth_headers(client)
    character_id = client.post("/characters", json={"name": "Рэм"}, headers=headers).json()["id"]
    calls = _stub_ask_sequence(
        monkeypatch,
        [
            {
                "answer": "ок",
                "sources": [],
                "proposed_changes": [{"path": "hp_current", "value": 10}],
            }
        ],
    )

    client.post(
        "/llm/ask",
        json={"question": "вопрос", "character_id": character_id},
        headers=headers,
    )

    assert len(calls) == 1


def test_a_retry_that_does_not_improve_keeps_the_first_attempt(client, monkeypatch) -> None:
    """The model's second guess is not automatically the better one — the
    player must not end up with less than the first pass already gave them."""
    headers = _auth_headers(client)
    character_id = client.post("/characters", json={"name": "Рэм"}, headers=headers).json()["id"]
    _stub_ask_sequence(
        monkeypatch,
        [
            {
                "answer": "Собрал.",
                "sources": [],
                "proposed_changes": [
                    {"path": "hp_current", "value": 10},
                    {"path": "owner_id", "value": 2},
                ],
            },
            {
                # The corrected attempt is worse: it drops the good change too.
                "answer": "",
                "sources": [],
                "proposed_changes": [{"path": "owner_id", "value": 2}],
            },
        ],
    )

    body = client.post(
        "/llm/ask",
        json={"question": "вопрос", "character_id": character_id},
        headers=headers,
    ).json()

    assert [change["path"] for change in body["proposed_changes"]] == ["hp_current"]
    assert len(body["rejected_changes"]) == 1


def test_the_retry_can_be_turned_off(client, monkeypatch) -> None:
    headers = _auth_headers(client)
    character_id = client.post("/characters", json={"name": "Рэм"}, headers=headers).json()["id"]
    monkeypatch.setattr(llm.settings, "sheet_edit_retry", False)
    calls = _stub_ask_sequence(
        monkeypatch,
        [{"answer": "ок", "sources": [], "proposed_changes": [{"path": "owner_id", "value": 2}]}],
    )

    client.post(
        "/llm/ask",
        json={"question": "вопрос", "character_id": character_id},
        headers=headers,
    )

    assert len(calls) == 1


def test_a_broken_retry_leaves_the_first_answer_standing(client, monkeypatch) -> None:
    """The correction step is best-effort: a player who already has a real
    answer must not lose it because the second call failed."""
    headers = _auth_headers(client)
    character_id = client.post("/characters", json={"name": "Рэм"}, headers=headers).json()["id"]
    calls: list[dict] = []

    def _fake_post(url, json, timeout):
        calls.append(json)
        if len(calls) == 1:
            return _FakeAskResponse(
                200,
                {
                    "answer": "Собрал.",
                    "sources": [],
                    "proposed_changes": [
                        {"path": "hp_current", "value": 10},
                        {"path": "x", "value": 1},
                    ],
                },
            )
        return _FakeAskResponse(503, {"detail": "not configured"})

    monkeypatch.setattr(llm.httpx, "post", _fake_post)

    body = client.post(
        "/llm/ask",
        json={"question": "вопрос", "character_id": character_id},
        headers=headers,
    ).json()

    assert len(calls) == 2
    assert [change["path"] for change in body["proposed_changes"]] == ["hp_current"]
