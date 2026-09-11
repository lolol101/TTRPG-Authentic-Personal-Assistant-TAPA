import os

# Must precede any app import: Settings is built when app.core.config is first
# imported, and the app now refuses to run without a real signing key.
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-long-enough-to-pass-validation")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402
from sqlmodel.pool import StaticPool  # noqa: E402

from app.core.db import get_session  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session_factory")
def session_factory_fixture(engine):
    """Opens a session on the same database the client is talking to.

    Lets a test check what actually landed in storage, rather than trusting
    the endpoint that just reported success.
    """

    def _open() -> Session:
        return Session(engine)

    return _open


@pytest.fixture(name="client")
def client_fixture(engine):
    def get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override

    # Not entering as a context manager: lifespan's init_db() targets the
    # real file-backed engine, which tests don't need — tables are created
    # above on the in-memory engine instead.
    test_client = TestClient(app)
    yield test_client

    app.dependency_overrides.clear()
