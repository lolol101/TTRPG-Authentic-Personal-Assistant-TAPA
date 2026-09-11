from pydantic_settings import BaseSettings

from app.core.paths import service_dir


def _default_dir(name: str) -> str:
    return (service_dir("dnd5e-data") / name).as_posix()


class Settings(BaseSettings):
    # Read by app.core.paths before Settings exists; declared so that having
    # it in .env is not rejected as an unknown key.
    tapa_data_dir: str = ""

    #: Official SRD 5.2.1, published by Wizards of the Coast under CC-BY-4.0.
    srd_url: str = "https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf"
    srd_filename: str = "SRD_CC_v5.2.1.pdf"

    source_dir: str = _default_dir("source")
    output_dir: str = _default_dir("chunks")

    #: The attribution CC-BY-4.0 requires us to carry with the content.
    attribution: str = (
        'This work includes material from the System Reference Document 5.2.1 ("SRD 5.2.1") '
        "by Wizards of the Coast LLC, available at https://www.dndbeyond.com/srd. "
        "Licensed under CC-BY-4.0."
    )
    source_book: str = "SRD 5.2.1"

    max_chunk_chars: int = 2000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
