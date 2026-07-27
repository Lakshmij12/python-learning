"""Performance smoke tests (marked; deselect with -m 'not performance').

These assert generous upper bounds so they catch pathological regressions
without being flaky on slow CI hardware.
"""

from __future__ import annotations

import os
import time

import pytest

from app.rag.chunker import chunk_text
from app.security.crypto import Cipher

pytestmark = pytest.mark.performance


def test_encryption_throughput() -> None:
    cipher = Cipher(os.urandom(32))
    payload = "a moderately sized message " * 20
    start = time.perf_counter()
    for _ in range(2000):
        cipher.decrypt(cipher.encrypt(payload))
    elapsed = time.perf_counter() - start
    # 2000 encrypt+decrypt round-trips should be well under 5s.
    assert elapsed < 5.0, f"crypto too slow: {elapsed:.2f}s"


def test_chunker_scales_to_large_documents() -> None:
    big_text = " ".join(f"token{i}" for i in range(50_000))
    start = time.perf_counter()
    chunks = chunk_text(big_text, chunk_size=800, overlap=100)
    elapsed = time.perf_counter() - start
    assert len(chunks) > 100
    assert elapsed < 2.0, f"chunker too slow: {elapsed:.2f}s"
