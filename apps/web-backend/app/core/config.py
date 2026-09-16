from pydantic_settings import BaseSettings

from app.core.paths import service_dir


def _default_database_url() -> str:
    path = (service_dir("web-backend") / "dev.db").as_posix()
    return f"sqlite:///{path}"


class Settings(BaseSettings):
    app_name: str = "web-backend"
    # Read by app.core.paths before Settings exists; declared so that having
    # it in .env is not rejected as an unknown key.
    tapa_data_dir: str = ""

    database_url: str = _default_database_url()

    # No default on purpose. A secret committed to the repository is not a
    # secret: anyone who has seen the code can forge any user's token.
    # verify_security_config() refuses to start without a real one.
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # Quotas, not policy: they keep one runaway script from filling the
    # database and burning a day of the provider's free tier. Generous enough
    # that ordinary play never meets them.
    max_chats_per_user: int = 50
    max_messages_per_chat: int = 500
    max_message_chars: int = 4000
    max_snapshots_per_character: int = 20

    # Where the built frontend lives. Empty means the sibling web-frontend's
    # dist/, which is what a plain checkout has; set it when the build is
    # deployed somewhere else. Missing build = API only, see core/frontend.py.
    frontend_dist_dir: str = ""

    llm_service_url: str = "http://localhost:8100"
    # A local 14B on the GPU thinks longer than a hosted model did.
    llm_request_timeout_seconds: float = 300.0
    # One extra round trip, only when the checker rejected part of a sheet
    # proposal: the model gets to read what it got wrong and try again once,
    # instead of the player just seeing a wall of "unavailable" paths.
    sheet_edit_retry: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
