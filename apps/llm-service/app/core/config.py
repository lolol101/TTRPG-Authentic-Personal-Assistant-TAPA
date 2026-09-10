from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "llm-service"

    # Ollama exposes an OpenAI-compatible API. Point this at a LAN address
    # (OLLAMA_HOST=0.0.0.0 on the Ollama machine) to use a remote GPU during
    # the pilot instead of running the model on this machine.
    ollama_base_url: str = "http://localhost:11434/v1"
    # gpt-oss:20b — MoE, ~3.6B active params, purpose-built by OpenAI for
    # local agentic/tool-calling use within 16GB VRAM. Fallback: qwen3:14b
    # if gpt-oss's response format doesn't play well with a given client.
    ollama_model: str = "gpt-oss:20b"
    llm_temperature: float = 0.7

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
