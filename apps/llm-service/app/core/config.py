from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "llm-service"

    # OpenAI-compatible endpoint. Both OpenRouter and Ollama speak this API,
    # so switching provider is a config change, not a code change.
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen3:14b"

    # "ollama" runs embeddings on the GPU through a local Ollama server;
    # "fastembed" is the CPU-only ONNX fallback for machines without one.
    embedding_backend: str = "ollama"
    embedding_model_id: str = "bge-m3"
    embedding_base_url: str = "http://localhost:11434"
    embedding_timeout_seconds: float = 120.0

    chroma_persist_dir: str = "./data/vector_db"
    chroma_collection: str = "pf2e_actions_ru"
    retrieval_k: int = 5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
