from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "web-backend"

    database_url: str = "sqlite:///./data/dev.db"

    jwt_secret_key: str = "dev-only-insecure-default-secret-change-me-in-env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    llm_service_url: str = "http://localhost:8100"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
