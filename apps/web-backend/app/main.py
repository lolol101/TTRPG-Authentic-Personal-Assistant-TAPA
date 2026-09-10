from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import auth, characters, health, llm
from app.core.config import settings
from app.core.db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(characters.router)
app.include_router(llm.router)
