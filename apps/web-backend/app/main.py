from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import auth, characters, chats, health, llm, snapshots
from app.core.config import settings
from app.core.db import init_db
from app.core.frontend import mount_frontend
from app.core.security import verify_security_config


@asynccontextmanager
async def lifespan(application: FastAPI):
    verify_security_config()
    init_db()
    # Here rather than at import: logging is configured by the server after
    # the module is imported, and mounting reports which mode we are in.
    # Routers are already registered by now, so "/" cannot shadow them.
    mount_frontend(application)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(characters.router)
app.include_router(chats.router)
app.include_router(snapshots.router)
app.include_router(llm.router)
