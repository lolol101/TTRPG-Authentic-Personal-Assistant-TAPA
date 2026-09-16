from pathlib import Path

from pydantic_settings import BaseSettings

from app.core.paths import service_dir


def _default_chroma_dir() -> str:
    return (service_dir("llm-service") / "vector_db").as_posix()


def _bundled_ca() -> str:
    """The Russian state roots shipped with the service — see certs/README.md.

    Kept out of `llm_ca_bundle` on purpose: a bundle there replaces the trust
    store for that provider outright, so handing these roots to an ordinary
    OpenAI-compatible endpoint would break its TLS instead of helping it.
    """
    return (Path(__file__).resolve().parents[2] / "certs" / "russian-trusted-ca.pem").as_posix()


class Settings(BaseSettings):
    app_name: str = "llm-service"
    # Read by app.core.paths before Settings exists; declared so that having
    # it in .env is not rejected as an unknown key.
    tapa_data_dir: str = ""

    # OpenAI-compatible endpoint. Both OpenRouter and Ollama speak this API,
    # so switching provider is a config change, not a code change.
    llm_provider_label: str = "ollama-local"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen3:14b"
    # "openai" for anything speaking that API; "gigachat" for the dialect —
    # see app/core/gigachat.py for what actually differs.
    llm_dialect: str = "openai"
    # GigaChat trades Basic credentials for a short-lived token instead of
    # taking a static key, and its endpoints need their own trust bundle.
    llm_auth_key: str = ""
    llm_ca_bundle: str = ""

    # Used when the primary is unreachable — the GPU machine being off should
    # degrade the app, not break it. Left empty means "no fallback".
    llm_fallback_provider_label: str = "openrouter"
    llm_fallback_base_url: str = "https://openrouter.ai/api/v1"
    llm_fallback_api_key: str = ""
    llm_fallback_model: str = "nvidia/nemotron-3.5-lightning:free"
    llm_fallback_dialect: str = "openai"
    llm_fallback_auth_key: str = ""
    llm_fallback_ca_bundle: str = ""

    # Only applies where we build the HTTP client ourselves, i.e. when a
    # provider needs its own trust bundle. httpx defaults to 5 seconds, which
    # no generation request survives — measured: the first GigaChat call timed
    # out and the answer silently fell through to the fallback provider.
    llm_timeout_seconds: float = 120.0

    gigachat_oauth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_timeout_seconds: float = 30.0
    # Used for a gigachat-dialect provider that names no bundle of its own.
    gigachat_ca_bundle: str = _bundled_ca()

    # "ollama" runs embeddings on the GPU through a local Ollama server;
    # "fastembed" is the CPU-only ONNX fallback for machines without one.
    embedding_backend: str = "ollama"
    embedding_model_id: str = "bge-m3"
    embedding_base_url: str = "http://localhost:11434"
    embedding_timeout_seconds: float = 120.0

    # Embeddings stay off the GPU so the generation model keeps the whole card.
    # A large model fills VRAM by itself; letting the embedder onto the GPU too
    # makes Ollama evict one for the other, and every ask pays a model reload
    # (~150s measured on a 30B MoE) twice. The embedder is small — CPU is fine.
    embedding_use_gpu: bool = False

    # Each embedding model has its own vector space, so each gets its own
    # collection — querying one model's index with another model's vectors
    # returns confident nonsense.
    embedding_fallback_backend: str = "fastembed"
    embedding_fallback_model_id: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    chroma_persist_dir: str = _default_chroma_dir()
    chroma_collection_prefix: str = "pf2e_actions_ru"
    retrieval_k: int = 5

    # The rulebooks are English; a Russian question finds the right page far
    # deeper in the results than the same question in English. Costs one
    # extra completion and one extra embedding per ordinary question — turn
    # it off to get the single plain search back.
    retrieval_rewrite_query: bool = True

    # What the dialogue may take of the model's window. The rules context is
    # retrieved fresh every turn and is the point of the app, so it is served
    # first; this is the leftover the chat history slides through.
    history_token_budget: int = 3000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()


def collection_name(model_id: str) -> str:
    """One collection per embedding model, derived from its name."""
    slug = "".join(char if char.isalnum() else "_" for char in model_id).strip("_").lower()
    return f"{settings.chroma_collection_prefix}__{slug}"
