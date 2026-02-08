import os
from typing import Literal

import torch
import getpass
from transformers import AutoModel, AutoTokenizer

model_id = "intfloat/e5-large-v2"


class EmbedderModelManager:
    def __init__(self, logger=None):
        self.logger = logger
        self.model = None
        self.tokenizer = None
        self.is_loaded = False

        if not os.environ.get("HF_TOKEN"):
            # os.environ["HF_TOKEN"] = getpass.getpass(f"{"HF_TOKEN"}: ")
            os.environ["HF_TOKEN"] = "..."

    def load_model(self):
        """Loads embedder model in memory (on GPU and/or CPU)"""
        try:
            if self.logger is not None:
                self.logger.info(f"Loading model: {model_id}")
            else:
                print(f"Loading model: {model_id}")

            self.tokenizer = AutoTokenizer.from_pretrained(model_id)
            self.model = AutoModel.from_pretrained(
                model_id, device_map="auto", low_cpu_mem_usage=True
            )

            self.model.eval()
            for param in self.model.parameters():
                param.requires_grad = False

            self.is_loaded = True

        except Exception as e:
            if self.logger is not None:
                self.logger.error(e)
            else:
                print(e)

    def __average_pool(
        self, last_hidden_states: torch.Tensor, attention_mask: torch.Tensor
    ) -> torch.Tensor:
        """Averages the hidden states of the last layer over the sequence length and attention mask."""
        last_hidden = last_hidden_states.masked_fill(
            ~attention_mask[..., None].bool(), 0.0
        )
        return last_hidden.sum(dim=1) / attention_mask.sum(dim=1)[..., None]

    def __encode(
        self,
        texts: list[str],
        task_type: Literal["query", "passage"] = "passage",
    ):
        """Encodes the given texts using the embedder model"""
        if not self.is_loaded:
            raise RuntimeError("Мodel isn't loaded")

        # Prepare texts for encoding with E5
        texts = [f"{task_type}: {text}" for text in texts]

        batch_dict = self.tokenizer(
            texts,
            max_length=512,
            padding=True,
            truncation=True,
            return_tensors="pt",
        )

        model_device = next(self.model.parameters()).device
        batch_dict = {
            key: value.to(model_device) for key, value in batch_dict.items()
        }

        with torch.no_grad():
            outputs = self.model(**batch_dict)
            embeddings = self.__average_pool(
                outputs.last_hidden_state, batch_dict["attention_mask"]
            )
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

        return embeddings.cpu().numpy()

    def embed_documents(self, texts):
        return self.__encode(texts, task_type="passage")

    def embed_query(self, text):
        return self.__encode([text], task_type="query")[0]
