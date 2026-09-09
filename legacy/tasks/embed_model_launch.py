import logging
import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

sys.path.append(os.path.abspath(".."))

from services import embedder_model_manager

# Setting up logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

embedder_model_manager = embedder_model_manager.ModelManager(logger)


class EmbeddingRequest(BaseModel):
    texts: list[str]


class EmbeddingResponse(BaseModel):
    embeddings: list[list[float]]


@asynccontextmanager
async def load_model_lifespan(app: FastAPI):
    logger.info("Loading model...")
    try:
        embedder_model_manager.load_model()
        logger.info("Model loaded successfully")
        yield
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise
    finally:
        logger.info("Application shutdown")


app = FastAPI(
    title="Text Embedding Service",
    version="1.0.0",
    lifespan=load_model_lifespan,
)


@app.post("/embed", response_model=EmbeddingResponse)
async def get_embeddings(request: EmbeddingRequest):
    """Getting ebmeddings for texts"""
    if not embedder_model_manager.is_loaded:
        raise HTTPException(status_code=503, detail="Model is not loaded")

    if not request.texts:
        raise HTTPException(
            status_code=400, detail="List of texts cannot be empty"
        )

    try:
        return EmbeddingResponse(
            embeddings=embedder_model_manager.encode(request.texts)
        )

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
