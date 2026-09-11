"""Where this machine keeps its data.

Everything the app cannot regenerate — the database, the vector index, the
scraped corpus — lives under one root so that moving to another machine is
copying a single folder. Each project claims its own subfolder of it.

Set TAPA_DATA_DIR to put that root anywhere, e.g. a roomier drive. Left
unset it stays beside the service, which is what a fresh clone expects.
"""

import os
from pathlib import Path

ENV_VAR = "TAPA_DATA_DIR"


def _from_env_file() -> str | None:
    """Reads the setting straight out of .env.

    Paths are needed while Settings is still being defined, so pydantic has
    not read .env yet — without this the variable would only work when
    exported into the real environment, which is a trap.
    """
    env_file = Path(".env")
    if not env_file.is_file():
        return None
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == ENV_VAR:
                return value.strip().strip('"').strip("'") or None
    except OSError:
        return None
    return None


def configured_root() -> str | None:
    return os.environ.get(ENV_VAR) or _from_env_file()


def data_root() -> Path:
    return Path(configured_root() or "./data").expanduser()


def service_dir(service: str) -> Path:
    """The subfolder a given service owns under the data root."""
    # Without a shared root each service keeps its historical ./data layout,
    # so an existing checkout keeps working untouched.
    return data_root() / service if configured_root() else data_root()
