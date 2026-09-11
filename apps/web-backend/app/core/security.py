from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

MINIMUM_SECRET_LENGTH = 32

# Values that have appeared as placeholders in this repo or its .env.example.
# Any of them means nobody set a real secret.
_KNOWN_PLACEHOLDERS = frozenset(
    {
        "dev-only-insecure-default-secret-change-me-in-env",
        "change-me-to-a-random-32-byte-secret",
        "change-me",
        "changeme",
        "secret",
    }
)


class InsecureConfigurationError(RuntimeError):
    """Raised when the app is configured in a way that cannot be safe."""


def verify_security_config() -> None:
    """Refuse to run without a real signing key.

    Called from the app's lifespan, so a misconfigured deployment fails
    loudly at startup instead of happily issuing forgeable tokens.
    """
    secret = settings.jwt_secret_key.strip()

    if not secret:
        raise InsecureConfigurationError(
            "JWT_SECRET_KEY не задан. Сгенерируй ключ и положи его в .env:\n"
            '    python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )

    if secret in _KNOWN_PLACEHOLDERS:
        raise InsecureConfigurationError(
            "JWT_SECRET_KEY — это значение-заглушка из репозитория. "
            "Любой, кто видел код, подделает токен любого пользователя. "
            "Сгенерируй настоящий ключ."
        )

    if len(secret) < MINIMUM_SECRET_LENGTH:
        raise InsecureConfigurationError(
            f"JWT_SECRET_KEY короче {MINIMUM_SECRET_LENGTH} символов "
            f"(сейчас {len(secret)}) — такой ключ перебирается."
        )


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(subject: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")
