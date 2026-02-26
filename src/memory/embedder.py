"""
Lazy-loaded fastembed embedder.

Uses sentence-transformers/all-MiniLM-L6-v2 (384-dim) for local embeddings via fastembed.
Falls back gracefully — sets _load_failed=True on any error, never retries.
Never imported at module level in calling code; always via memory_store.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_DIMS = 384

_model = None
_load_failed = False


def _load_model():
    """Load the embedding model on first call. Thread-safe by Python GIL on CPython."""
    global _model, _load_failed

    if _load_failed or _model is not None:
        return _model

    try:
        # Ensure the model is loaded from the pre-baked image path, not downloaded
        models_dir = os.environ.get("AIO_MODELS_DIR", "/app/fastembed_cache")
        os.environ.setdefault("FASTEMBED_CACHE_PATH", models_dir)

        from fastembed import TextEmbedding  # noqa: PLC0415

        _model = TextEmbedding(model_name=MODEL_NAME, cache_dir=models_dir)
        logger.info("[Memory] fastembed embedder loaded: %s (%d dims)", MODEL_NAME, MODEL_DIMS)
        print(f"[Memory] fastembed embedder ready: {MODEL_NAME}", flush=True)
        return _model

    except Exception as exc:
        _load_failed = True
        logger.warning(
            "[Memory] Embedder unavailable — cross-session memory disabled. Reason: %s",
            exc,
        )
        print(f"[Memory] Embedder FAILED to load: {exc}", flush=True)
        return None


def embed(text: str) -> Optional[list[float]]:
    """
    Embed text into a 384-dim normalized float vector.
    Returns None if embedder is unavailable (agent continues without memory).
    """
    model = _load_model()
    if model is None:
        return None
    try:
        vec = next(model.embed([text])).astype(np.float32)
        return vec.tolist()
    except Exception as exc:
        logger.error("[Memory] Embedding failed: %s", exc)
        return None


def is_available() -> bool:
    """Return True if embedder loaded successfully."""
    return _load_model() is not None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two pre-normalized vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(ai * bi for ai, bi in zip(a, b))
    # Vectors are normalized (unit length), so dot product IS cosine similarity
    # Clamp to [-1, 1] to guard against float precision issues
    return max(-1.0, min(1.0, dot))
