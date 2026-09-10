from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "llm-service"

    # OpenAI-compatible endpoint. Both OpenRouter and Ollama speak this API,
    # so switching provider is a config change, not a code change.
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    llm_model: str = "nvidia/nemotron-3.5-lightning:free"

    # Light multilingual ONNX model (fastembed, no PyTorch) — deliberately
    # picked over a transformers/torch model, which crashed with MemoryError
    # loading weights on this low-RAM dev machine. Swap for a heavier model
    # once a GPU/more RAM is available — nothing else changes.
    embedding_model_id: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    chroma_persist_dir: str = "./data/vector_db"
    chroma_collection: str = "pf2e_actions_ru"
    retrieval_k: int = 5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
