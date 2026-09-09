import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.db import get_session
from app.main import app


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

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
