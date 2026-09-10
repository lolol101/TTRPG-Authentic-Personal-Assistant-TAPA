from fastapi import FastAPI

from app.api import chat
from app.core.config import settings

app = FastAPI(title=settings.app_name)

app.include_router(chat.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
