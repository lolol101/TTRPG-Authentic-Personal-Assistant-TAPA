from pydantic_settings import BaseSettings

from app.core.paths import service_dir


def _default_dir(name: str) -> str:
    return (service_dir("pf2e-data") / name).as_posix()


class Settings(BaseSettings):
    # Read by app.core.paths before Settings exists; declared so that having
    # it in .env is not rejected as an unknown key.
    tapa_data_dir: str = ""

    site_base_url: str = "https://pf2.ru"
    sitemap_url: str = "https://pf2.ru/sitemap.xml"

    cache_dir: str = _default_dir("html_cache")
    output_dir: str = _default_dir("chunks")

    user_agent: str = "TAPA-pf2e-data/0.1 (research assistant; contact via github.com/lolol101)"
    rate_limit_seconds: float = 1.0

    # Plain-text chunks longer than this are split on paragraph breaks.
    max_chunk_chars: int = 2000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
