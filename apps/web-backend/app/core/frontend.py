"""Serving the built frontend from the backend.

Publishing means one address, not two: the backend serves the frontend's
build output, so there is no second origin to open up through CORS and no
Vite dev server facing the internet — it is explicitly not built for that.

In development nothing is mounted: `npm run dev` serves the frontend and
proxies the API here, which is why a missing build is normal, not an error.
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings

_log = logging.getLogger(__name__)


def default_dist_dir() -> Path:
    """Where `npm run build` leaves the frontend in a plain checkout."""
    # .../apps/web-backend/app/core/frontend.py -> core -> app -> web-backend
    return Path(__file__).resolve().parents[3] / "web-frontend" / "dist"


def frontend_dist_dir() -> Path:
    """The build to serve: FRONTEND_DIST_DIR if set, else the sibling app."""
    configured = settings.frontend_dist_dir.strip()
    return Path(configured).expanduser() if configured else default_dist_dir()


def mount_frontend(app: FastAPI, dist_dir: Path | None = None) -> bool:
    """Mounts the built frontend at the root. Returns whether it mounted.

    Must be called after the API routers: Starlette matches routes in the
    order they were added, and a mount at "/" added earlier would swallow
    every endpoint behind it.
    """
    dist = dist_dir if dist_dir is not None else frontend_dist_dir()

    # A folder without index.html is an interrupted or never-run build.
    # Mounting it would answer 404 for the app itself and hide the reason,
    # so say it out loud instead.
    if not (dist / "index.html").is_file():
        _log.info("Фронтенд не смонтирован: сборки нет в %s (в разработке это норма)", dist)
        return False

    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    _log.info("Фронтенд раздаётся из %s", dist)
    return True
