"""Multilingual sentence embeddings, computed locally with ONNX (no API, no GPU)."""

import threading

import numpy as np

from app import config

_model = None
_lock = threading.Lock()


def model():
    global _model
    with _lock:
        if _model is None:
            from fastembed import TextEmbedding

            _model = TextEmbedding(config.EMBED_MODEL)
    return _model


def embed(texts: list[str]) -> np.ndarray:
    """Unit-length float32 vectors, so a dot product is the cosine similarity."""
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    vectors = np.array(list(model().embed(texts, batch_size=32)), dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-12
    return vectors


def to_blob(vector: np.ndarray) -> bytes:
    return vector.astype(np.float32).tobytes()


def from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)
