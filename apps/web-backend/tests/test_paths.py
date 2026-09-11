import importlib

from app.core import paths


def test_defaults_to_the_folder_beside_the_service(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv(paths.ENV_VAR, raising=False)
    # paths also consults ./.env, so run where the developer's own one cannot
    # decide the result.
    monkeypatch.chdir(tmp_path)

    # A fresh clone must keep working with no configuration at all.
    assert paths.service_dir("web-backend").as_posix() == "data"


def test_reads_the_root_from_a_dotenv_file(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv(paths.ENV_VAR, raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(f"{paths.ENV_VAR}=D:/TAPA-data\n", encoding="utf-8")

    assert paths.service_dir("llm-service").as_posix() == "D:/TAPA-data/llm-service"


def test_an_exported_variable_wins_over_the_dotenv_file(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(f"{paths.ENV_VAR}=D:/from-file\n", encoding="utf-8")
    monkeypatch.setenv(paths.ENV_VAR, "E:/from-environment")

    assert paths.data_root().as_posix() == "E:/from-environment"


def test_a_shared_root_gives_each_service_its_own_subfolder(monkeypatch) -> None:
    monkeypatch.setenv(paths.ENV_VAR, "D:/TAPA-data")

    assert paths.service_dir("web-backend").as_posix() == "D:/TAPA-data/web-backend"
    assert paths.service_dir("llm-service").as_posix() == "D:/TAPA-data/llm-service"


def test_the_database_follows_the_data_root(monkeypatch) -> None:
    monkeypatch.setenv(paths.ENV_VAR, "D:/TAPA-data")

    from app.core import config

    reloaded = importlib.reload(config)
    try:
        # _env_file=None ignores the developer's local .env, which would
        # otherwise decide the outcome of this test on their machine.
        settings = reloaded.Settings(_env_file=None)
        assert settings.database_url == "sqlite:///D:/TAPA-data/web-backend/dev.db"
    finally:
        # Other tests share this module; leave it as they expect to find it.
        monkeypatch.delenv(paths.ENV_VAR, raising=False)
        importlib.reload(config)
