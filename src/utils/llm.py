"""LLM client factory — Groq inference."""

from __future__ import annotations

import os

from langchain_groq import ChatGroq


def get_llm(temperature: float = 0.0) -> ChatGroq:
    """Return a configured ChatGroq instance."""
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    return ChatGroq(model=model, temperature=temperature)
