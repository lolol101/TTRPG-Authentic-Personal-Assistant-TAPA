from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

from app.core.paths import service_dir


def _default_chroma_dir() -> str:
    return (service_dir("llm-service") / "vector_db").as_posix()


def _bundled_ca() -> str:
    """The Russian state roots shipped with the service — see certs/README.md.

    Kept out of `llm_ca_bundle` on purpose: a bundle there replaces the trust
    store for that provider outright, so handing these roots to an ordinary
    OpenAI-compatible endpoint would break its TLS instead of helping it.
    """
    return (Path(__file__).resolve().parents[2] / "certs" / "russian-trusted-ca.pem").as_posix()


class Settings(BaseSettings):
    app_name: str = "llm-service"
    # Read by app.core.paths before Settings exists; declared so that having
    # it in .env is not rejected as an unknown key.
    tapa_data_dir: str = ""

    # OpenAI-compatible endpoint. Both OpenRouter and Ollama speak this API,
    # so switching provider is a config change, not a code change.
    llm_provider_label: str = "ollama-local"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen3:14b"
    # "openai" for anything speaking that API; "gigachat" for the dialect —
    # see app/core/gigachat.py for what actually differs.
    llm_dialect: str = "openai"
    # GigaChat trades Basic credentials for a short-lived token instead of
    # taking a static key, and its endpoints need their own trust bundle.
    llm_auth_key: str = ""
    llm_ca_bundle: str = ""

    # Used when the primary is unreachable — the GPU machine being off should
    # degrade the app, not break it. Left empty means "no fallback".
    llm_fallback_provider_label: str = "openrouter"
    llm_fallback_base_url: str = "https://openrouter.ai/api/v1"
    llm_fallback_api_key: str = ""
    llm_fallback_model: str = "nvidia/nemotron-3.5-lightning:free"
    llm_fallback_dialect: str = "openai"
    llm_fallback_auth_key: str = ""
    llm_fallback_ca_bundle: str = ""

    # Only applies where we build the HTTP client ourselves, i.e. when a
    # provider needs its own trust bundle. httpx defaults to 5 seconds, which
    # no generation request survives — measured: the first GigaChat call timed
    # out and the answer silently fell through to the fallback provider.
    llm_timeout_seconds: float = 120.0

    gigachat_oauth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_timeout_seconds: float = 30.0
    # Used for a gigachat-dialect provider that names no bundle of its own.
    gigachat_ca_bundle: str = _bundled_ca()

    # "ollama" runs embeddings on the GPU through a local Ollama server;
    # "fastembed" is the CPU-only ONNX fallback for machines without one.
    embedding_backend: str = "ollama"
    embedding_model_id: str = "bge-m3"
    embedding_base_url: str = "http://localhost:11434"
    embedding_timeout_seconds: float = 120.0

    # Retries inside one embedding call. A full re-index is hours of
    # back-to-back requests to a local server, and a single transient
    # timeout used to end the whole run — measured, one did, 2029 chunks
    # into 13511. Retried in place rather than failed over: the fallback
    # embeds into a different vector space, and switching mid-corpus would
    # leave one collection holding two.
    embedding_retry_attempts: int = 3
    embedding_retry_backoff_seconds: float = 2.0

    # Embeddings stay off the GPU so the generation model keeps the whole card.
    # A large model fills VRAM by itself; letting the embedder onto the GPU too
    # makes Ollama evict one for the other, and every ask pays a model reload
    # (~150s measured on a 30B MoE) twice. The embedder is small — CPU is fine.
    embedding_use_gpu: bool = False

    # Each embedding model has its own vector space, so each gets its own
    # collection — querying one model's index with another model's vectors
    # returns confident nonsense.
    embedding_fallback_backend: str = "fastembed"
    embedding_fallback_model_id: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    chroma_persist_dir: str = _default_chroma_dir()

    # Names the generation of the corpus, not just the game system: the
    # chunks carry the whole stat block — prerequisites, action cost, price,
    # Bulk — where the previous build had only level and traits. Switching
    # the prefix is what promotes a freshly built index, and switching it
    # back is the rollback, because each generation keeps its own collection
    # rather than overwriting the one being served.
    #
    # (The old "pf2e_actions_ru" was a stale name besides: the corpus has
    # been the English Foundry packs, not Russian pf2.ru action pages, since
    # that source was replaced.)
    chroma_collection_prefix: str = "pf2e_statblock"
    retrieval_k: int = 5

    # The rulebooks are English; a Russian question finds the right page far
    # deeper in the results than the same question in English. Costs one
    # extra completion and one extra embedding per ordinary question — turn
    # it off to get the single plain search back.
    retrieval_rewrite_query: bool = True

    # How many rules one question may be searched for separately. A question
    # naming two of them ("можно ли схватить, если я напуган") loses one
    # entirely when it is named as a single query — measured, 8 of 12
    # concepts retrieved against 11 of 12 when each got its own query. Each
    # one past the first costs an embedding and a search, not a completion,
    # but they all land in the same prompt: past a few, the context the
    # retrieval exists to protect is what is being spent. 1 restores the
    # single-query behaviour.
    retrieval_max_search_queries: int = 3

    # How much of the chat the rewrite sees when it restates a question so it
    # reads without the dialogue. Enough for "а если он…" or "второй вариант"
    # to find what they point at; assistant answers are cut short because
    # what a follow-up leans on sits near their start, and long prose only
    # slows the call.
    rewrite_history_messages: int = 4
    rewrite_history_answer_chars: int = 400

    # On a sheet-building request, restrict each area's search to the chunk
    # categories that area can actually be answered from. Measured on the
    # live index: a build-style query put 2.44 of 5 context slots in the
    # right section, and "fighter class features level 1" put 0 of 5 —
    # five archetype feats and no class feature at all. Filtered, 5 of 5.
    # Ordinary questions stay unfiltered: there the same measurement moved
    # 11 of 12 cases to 12 of 12, which is not worth the risk of a wrong
    # filter. Turn this off to search the whole index for every area.
    retrieval_filter_by_section: bool = True

    # Chroma's l2 distance of the closest hit to the query embedding.
    # bge-m3, this index, 2026-09-22: an English-rewritten question whose
    # answer is actually indexed ("Grapple action", "Demoralize action",
    # "Frightened condition") landed its nearest hit between 0.62 and 0.69;
    # a question with no business in a PF2e corpus ("capital of France",
    # "17 times 34") never landed closer than 0.90. 0.85 sits in the gap
    # with margin on both sides. Retrieval is never cut on this — see
    # retriever.is_weak — only flagged, because four questions on each side
    # is a spot check, not a calibration, and a hard cut risks losing a
    # genuine answer to a threshold set from too little data. Revisit once
    # the golden set is broad enough to measure the trade-off properly.
    retrieval_weak_distance: float = 0.85

    # Hits farther than this are dropped before the model sees them — the
    # coarse cut against outright garbage, not the judgement of relevance
    # (that is context_mode's job). Off-topic questions never landed closer
    # than 0.90 and the first cut sat exactly there; it was loosened to 0.95
    # so borderline pages reach the selector, which now keeps related pages
    # too. The price: an off-topic question with hits in 0.90-0.95 pays for
    # a selection call that should come back empty. Only for "off" does
    # this cut alone decide what the answer reads.
    retrieval_max_distance: float = 0.95

    # What stands between retrieval and the answer:
    #   "off"    — every hit within retrieval_max_distance goes in as is;
    #   "select" — one extra call names which hits bear on the question, and
    #              only those go in, verbatim;
    #   "digest" — one extra call writes a condensed extract from the hits,
    #              and the answer is built from that instead of the pages.
    # select and digest are candidates measured against each other by
    # evals/compare_context_modes.py; see app/core/context_select.py.
    context_mode: Literal["off", "select", "digest"] = "off"

    # What the dialogue may take of the model's window. The rules context is
    # retrieved fresh every turn and is the point of the app, so it is served
    # first; this is the leftover the chat history slides through.
    history_token_budget: int = 3000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()


def collection_name(model_id: str) -> str:
    """One collection per embedding model, derived from its name."""
    slug = "".join(char if char.isalnum() else "_" for char in model_id).strip("_").lower()
    return f"{settings.chroma_collection_prefix}__{slug}"
