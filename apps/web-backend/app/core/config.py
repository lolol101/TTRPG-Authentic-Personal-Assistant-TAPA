from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "web-backend"

    database_url: str = "sqlite:///./data/dev.db"

    # No default on purpose. A secret committed to the repository is not a
    # secret: anyone who has seen the code can forge any user's token.
    # verify_security_config() refuses to start without a real one.
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    llm_service_url: str = "http://localhost:8100"
    # A local 14B on the GPU thinks longer than a hosted model did.
    llm_request_timeout_seconds: float = 300.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
