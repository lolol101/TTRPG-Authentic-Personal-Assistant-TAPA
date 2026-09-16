"""Раздача собранного фронтенда самим бэкендом.

Публикация — это один адрес наружу, а не два, поэтому статику отдаёт
бэкенд. Тесты держат два обещания: API не должен пострадать от монтирования
в корень, а отсутствующая сборка не должна ронять сервис.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.frontend import default_dist_dir, mount_frontend


def _built_frontend(tmp_path: Path) -> Path:
    """Минимальная сборка: то, что оставляет `npm run build`."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>TAPA</title>", encoding="utf-8")
    (dist / "assets" / "app-a1b2c3.js").write_text("console.log('tapa')", encoding="utf-8")
    return dist


def _app_with_api() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_serves_index_at_root(tmp_path: Path) -> None:
    app = _app_with_api()
    mount_frontend(app, _built_frontend(tmp_path))

    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "TAPA" in response.text


def test_serves_hashed_assets(tmp_path: Path) -> None:
    app = _app_with_api()
    mount_frontend(app, _built_frontend(tmp_path))

    response = TestClient(app).get("/assets/app-a1b2c3.js")

    assert response.status_code == 200
    assert "console.log" in response.text


def test_api_routes_win_over_static_mount(tmp_path: Path) -> None:
    """Монтирование в корень не должно проглатывать эндпоинты."""
    app = _app_with_api()
    mount_frontend(app, _built_frontend(tmp_path))

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_missing_build_is_not_fatal(tmp_path: Path) -> None:
    """В разработке фронт поднимает Vite, сборки рядом нет — это норма."""
    app = _app_with_api()

    mounted = mount_frontend(app, tmp_path / "dist")

    assert mounted is False
    assert TestClient(app).get("/health").status_code == 200


def test_build_without_index_is_refused(tmp_path: Path) -> None:
    """Папка без index.html — оборванная сборка, а не фронтенд."""
    half_built = tmp_path / "dist"
    (half_built / "assets").mkdir(parents=True)
    app = _app_with_api()

    assert mount_frontend(app, half_built) is False


def test_default_dist_dir_is_the_frontend_build_folder() -> None:
    assert default_dist_dir().parts[-2:] == ("web-frontend", "dist")
