"""LLM provider access, kept behind one seam so swapping Ollama for a cloud
provider later is a config change here, not a rewrite of call sites."""

from __future__ import annotations

from openai import OpenAI

from app.core.config import settings


def _get_client() -> OpenAI:
    return OpenAI(api_key="ollama", base_url=settings.ollama_base_url)


def complete(message: str) -> str:
    """Send a single user message to the configured model, return its reply."""
    client = _get_client()
    response = client.chat.completions.create(
        model=settings.ollama_model,
        messages=[{"role": "user", "content": message}],
        temperature=settings.llm_temperature,
    )
    return response.choices[0].message.content or ""
