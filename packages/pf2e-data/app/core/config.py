from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    site_base_url: str = "https://pf2.ru"
    sitemap_url: str = "https://pf2.ru/sitemap.xml"

    cache_dir: str = "./data/html_cache"
    output_dir: str = "./data/chunks"

    user_agent: str = "TAPA-pf2e-data/0.1 (research assistant; contact via github.com/lolol101)"
    rate_limit_seconds: float = 1.0

    # Plain-text chunks longer than this are split on paragraph breaks.
    max_chunk_chars: int = 2000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
