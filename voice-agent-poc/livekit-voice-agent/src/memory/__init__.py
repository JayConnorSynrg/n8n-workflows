"""
AIO Voice System — Persistent Memory Layer

Cross-session memory backed by SQLite with hybrid vector + BM25 search.
Gracefully disabled if sentence-transformers is unavailable.

Import safety: this module is safe to import even if dependencies are missing.
The MEMORY_AVAILABLE flag signals availability to callers.
"""
from __future__ import annotations

# Populated by memory_store on first successful init
MEMORY_AVAILABLE: bool = False
