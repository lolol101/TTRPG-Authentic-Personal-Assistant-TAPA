from __future__ import annotations

import logging
from typing import Literal

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from config.settings import settings

_log = logging.getLogger(__name__)

class EmbedderModelManager:
    """Loads and runs the embedding model for ChromaDB."""

    def __init__(self) -> None:
        self.model: AutoModel | None = None
        self.tokenizer: AutoTokenizer | None = None
        self.is_loaded = False

    def load_model(self) -> None:
        """Load the embedder into memory (GPU via accelerate, or CPU)."""
        model_id = settings.embedding_model_id
        _log.info("Loading embedding model: %s", model_id)

        self.tokenizer = AutoTokenizer.from_pretrained(model_id)

        self.model = AutoModel.from_pretrained(
            model_id, device_map="auto", low_cpu_mem_usage=True,
        )

        self.model.eval()
        for param in self.model.parameters():
            param.requires_grad = False

        self.is_loaded = True
        _log.info("Embedding model loaded.")

    def _average_pool(
        self,
        last_hidden_states: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> torch.Tensor:
        last_hidden = last_hidden_states.masked_fill(
            ~attention_mask[..., None].bool(), 0.0,
        )
        return last_hidden.sum(dim=1) / attention_mask.sum(dim=1)[..., None]

    def _encode(
        self,
        texts: list[str],
        task_type: Literal["query", "passage"] = "passage",
    ) -> np.ndarray:
        if not self.is_loaded:
            raise RuntimeError("Embedding model is not loaded")

        texts = [f"{task_type}: {text}" for text in texts]
        batch_dict = self.tokenizer(
            texts, max_length=512, padding=True, truncation=True, return_tensors="pt",
        )

        device = next(self.model.parameters()).device
        batch_dict = {k: v.to(device) for k, v in batch_dict.items()}

        with torch.no_grad():
            outputs = self.model(**batch_dict)
            embeddings = self._average_pool(
                outputs.last_hidden_state, batch_dict["attention_mask"],
            )
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

        return embeddings.cpu().numpy()

    # LangChain Embeddings interface
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts, task_type="passage").tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text], task_type="query")[0].tolist()
