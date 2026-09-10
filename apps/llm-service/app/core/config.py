from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "llm-service"

    # OpenAI-compatible endpoint. Both OpenRouter and Ollama speak this API,
    # so switching provider is a config change, not a code change.
    llm_provider_label: str = "ollama-local"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen3:14b"

    # Used when the primary is unreachable — the GPU machine being off should
    # degrade the app, not break it. Left empty means "no fallback".
    llm_fallback_provider_label: str = "openrouter"
    llm_fallback_base_url: str = "https://openrouter.ai/api/v1"
    llm_fallback_api_key: str = ""
    llm_fallback_model: str = "nvidia/nemotron-3.5-lightning:free"

    # "ollama" runs embeddings on the GPU through a local Ollama server;
    # "fastembed" is the CPU-only ONNX fallback for machines without one.
    embedding_backend: str = "ollama"
    embedding_model_id: str = "bge-m3"
    embedding_base_url: str = "http://localhost:11434"
    embedding_timeout_seconds: float = 120.0

    # Each embedding model has its own vector space, so each gets its own
    # collection — querying one model's index with another model's vectors
    # returns confident nonsense.
    embedding_fallback_backend: str = "fastembed"
    embedding_fallback_model_id: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    chroma_persist_dir: str = "./data/vector_db"
    chroma_collection_prefix: str = "pf2e_actions_ru"
    retrieval_k: int = 5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()


def collection_name(model_id: str) -> str:
    """One collection per embedding model, derived from its name."""
    slug = "".join(char if char.isalnum() else "_" for char in model_id).strip("_").lower()
    return f"{settings.chroma_collection_prefix}__{slug}"
