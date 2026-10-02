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

    # pf2.ru answers 403/429 while its limit lasts and sends no Retry-After,
    # so a refused page is retried after a doubling wait. Past the total the
    # section stops and scripts/download_corpus.ps1 takes over the waiting.
    refusal_backoff_seconds: float = 60.0
    refusal_backoff_max_seconds: float = 900.0
    refusal_max_wait_seconds: float = 3600.0
    # The same refusal can come as HTTP 200 with this page in place of the rule.
    refusal_page_marker: str = "ПОДОЗРИТЕЛЬНАЯ АКТИВНОСТЬ"

    # Plain-text chunks longer than this are split on paragraph breaks.
    max_chunk_chars: int = 2000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
