from openai import OpenAI

from app.core.config import settings


class LLMNotConfiguredError(RuntimeError):
    pass


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if not settings.llm_api_key:
        raise LLMNotConfiguredError(
            "LLM_API_KEY is not set — add it to .env (see .env.example)."
        )
    if _client is None:
        _client = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
    return _client


def get_completion(message: str) -> str:
    """Send a single user message to the configured LLM and return its reply.

    No conversation history, no tools, no retrieval — this only proves the
    provider wiring (config -> real LLM response). RAG comes later.
    """
    client = _get_client()
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": message}],
    )
    return response.choices[0].message.content or ""
