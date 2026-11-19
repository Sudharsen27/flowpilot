"""Embedding provider protocol and OpenAI-compatible implementation."""

from __future__ import annotations

import json
import logging
import math
from typing import Protocol

from app.core.config import settings
from app.core.exceptions import ProviderNotConfiguredError

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""


class NullEmbeddingProvider:
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise ProviderNotConfiguredError("Embedding provider is not configured")


class OpenAICompatibleEmbeddingProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        timeout_seconds: float = 30,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.timeout_seconds = timeout_seconds

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise ProviderNotConfiguredError("OpenAI SDK is not installed") from exc
        client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout_seconds,
        )
        response = client.embeddings.create(model=self.model, input=texts)
        by_index = {item.index: list(item.embedding) for item in response.data}
        return [by_index[index] for index in range(len(texts))]


def create_embedding_provider() -> EmbeddingProvider | None:
    if not settings.embedding_provider_enabled:
        return None
    secret = settings.openai_api_key
    if not secret:
        return None
    base_url = getattr(settings, "openai_base_url", None)
    return OpenAICompatibleEmbeddingProvider(
        api_key=secret,
        model=settings.embedding_model,
        base_url=base_url,
        timeout_seconds=settings.openai_request_timeout_seconds,
    )


def dump_embedding(vector: list[float]) -> str:
    return json.dumps(vector)


def load_embedding(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(loaded, list) or not loaded:
        return None
    try:
        return [float(value) for value in loaded]
    except (TypeError, ValueError):
        return None


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for a, b in zip(left, right, strict=True):
        dot += a * b
        left_norm += a * a
        right_norm += b * b
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot / math.sqrt(left_norm * right_norm)
