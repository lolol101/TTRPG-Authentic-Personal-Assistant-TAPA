from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5:7b-instruct"

    telegram_bot_token: str = ""

    chroma_persist_dir: str = "./data/vector_db"
    chroma_collection: str = "books_collection"

    embedding_model_id: str = "intfloat/e5-large-v2"

    scraper_rate_limit: float = 1.0
    scraper_cache_dir: str = "./data/books_sources"

    langsmith_tracing: bool = False
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langchain_api_key: str = ""
    langchain_project: str = "TTRPG-Authentic-Personal-Assistant-TAPA"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
