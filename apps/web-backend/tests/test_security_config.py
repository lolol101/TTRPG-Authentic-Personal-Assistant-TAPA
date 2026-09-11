import pytest

from app.core import security
from app.core.security import InsecureConfigurationError, verify_security_config

REAL_SECRET = "b7f3c1e9a4d25f80c6b1a93e7d4058fc2a6e19b3d8c47051"


def _set_secret(monkeypatch, value: str) -> None:
    monkeypatch.setattr(security.settings, "jwt_secret_key", value)


def test_accepts_a_real_secret(monkeypatch) -> None:
    _set_secret(monkeypatch, REAL_SECRET)

    verify_security_config()


def test_refuses_to_start_without_a_secret(monkeypatch) -> None:
    _set_secret(monkeypatch, "")

    with pytest.raises(InsecureConfigurationError, match="не задан"):
        verify_security_config()


def test_refuses_whitespace_only_secret(monkeypatch) -> None:
    _set_secret(monkeypatch, "   ")

    with pytest.raises(InsecureConfigurationError, match="не задан"):
        verify_security_config()


@pytest.mark.parametrize(
    "placeholder",
    [
        "dev-only-insecure-default-secret-change-me-in-env",
        "change-me-to-a-random-32-byte-secret",
        "change-me",
    ],
)
def test_refuses_placeholders_that_ship_in_the_repo(monkeypatch, placeholder: str) -> None:
    _set_secret(monkeypatch, placeholder)

    with pytest.raises(InsecureConfigurationError, match="заглушка|короче"):
        verify_security_config()


def test_refuses_a_short_secret(monkeypatch) -> None:
    _set_secret(monkeypatch, "too-short")

    with pytest.raises(InsecureConfigurationError, match="короче"):
        verify_security_config()


def test_config_ships_no_secret_of_its_own() -> None:
    """The repository itself must never carry a usable signing key."""
    from app.core.config import Settings

    assert Settings.model_fields["jwt_secret_key"].default == ""


def test_startup_refuses_a_misconfigured_app(monkeypatch) -> None:
    """The check is wired into lifespan, not merely available to call."""
    from fastapi.testclient import TestClient

    from app.main import app

    _set_secret(monkeypatch, "")

    with pytest.raises(InsecureConfigurationError):
        with TestClient(app):
            pass
