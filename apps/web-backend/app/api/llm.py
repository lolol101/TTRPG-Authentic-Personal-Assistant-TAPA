import httpx
from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.schemas.ask import AskRequest, AskResponse

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/ping")
def ping() -> dict:
    try:
        response = httpx.get(f"{settings.llm_service_url}/health", timeout=5.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"llm-service unreachable: {exc}",
        ) from exc

    return response.json()


@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> dict:
    try:
        response = httpx.post(
            f"{settings.llm_service_url}/ask",
            json=payload.model_dump(),
            timeout=60.0,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"llm-service unreachable: {exc}",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    return response.json()
