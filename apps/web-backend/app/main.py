from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import auth, characters, chats, health, llm, snapshots
from app.core.config import settings
from app.core.db import init_db
from app.core.security import verify_security_config


@asynccontextmanager
async def lifespan(_: FastAPI):
    verify_security_config()
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(characters.router)
app.include_router(chats.router)
app.include_router(snapshots.router)
app.include_router(llm.router)
