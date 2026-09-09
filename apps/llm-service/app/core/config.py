from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "llm-service"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
