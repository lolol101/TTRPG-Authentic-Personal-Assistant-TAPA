from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "llm-service"

    # Ollama exposes an OpenAI-compatible API. Point this at a LAN address
    # (OLLAMA_HOST=0.0.0.0 on the Ollama machine) to use a remote GPU during
    # the pilot instead of running the model on this machine.
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5:14b-instruct"
    llm_temperature: float = 0.7

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
