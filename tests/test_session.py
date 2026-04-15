from bot.session import SessionStore, UserSession


class TestSessionStore:
    def test_get_creates_new_session(self):
        store = SessionStore()
        session = store.get(123)
        assert isinstance(session, UserSession)
        assert session.book_name is None

    def test_get_returns_same_session(self):
        store = SessionStore()
        s1 = store.get(42)
        s1.book_name = "pf2e"
        s2 = store.get(42)
        assert s2.book_name == "pf2e"
        assert s1 is s2

    def test_reset_clears_session(self):
        store = SessionStore()
        store.get(99).book_name = "starfinder"
        store.reset(99)
        fresh = store.get(99)
        assert fresh.book_name is None

    def test_different_users_have_different_sessions(self):
        store = SessionStore()
        store.get(1).book_name = "pf2e"
        store.get(2).book_name = "sf1e"
        assert store.get(1).book_name == "pf2e"
        assert store.get(2).book_name == "sf1e"
