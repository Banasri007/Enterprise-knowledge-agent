"""LLM client factory — Groq inference."""

from __future__ import annotations

import os

from langchain_groq import ChatGroq


def get_llm(temperature: float = 0.0, fast: bool = False) -> ChatGroq:
    """Return a configured ChatGroq instance.

    Grading/reconciliation/query-rewrite steps don't need the biggest model —
    they're structured JSON judgments, not open-ended writing — so callers
    that aren't generating the final user-facing answer should pass
    fast=True. This is the main lever for cutting per-question latency,
    since a full pass through the graph makes 3-6 sequential LLM calls.
    """
    if fast:
        model = os.getenv("GROQ_FAST_MODEL", "llama-3.1-8b-instant")
    else:
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    return ChatGroq(model=model, temperature=temperature)
