"""Embedding and vector store utilities using ChromaDB."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import chromadb
import streamlit as st
from chromadb.config import Settings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

DOCS_COLLECTION = "docs_corpus"
GITHUB_COLLECTION = "github_history"


@st.cache_resource(show_spinner=False)
def get_embeddings() -> HuggingFaceEmbeddings:
    """Local sentence-transformer embeddings (Groq has no embedding API).

    Uses st.cache_resource instead of functools.lru_cache: a plain
    lru_cache on a module-level function isn't reliably preserved across
    Streamlit's dev-mode file-watcher reruns, so the ~90MB model could
    silently get reloaded from disk on reruns that shouldn't have touched
    it. st.cache_resource is Streamlit's purpose-built fix for exactly
    this (models, DB connections) and survives reruns properly.

    show_spinner=False: this is called from inside LangGraph node functions
    (docs_agent_node etc.), which LangGraph runs in worker threads with no
    Streamlit ScriptRunContext. The default spinner tries to enqueue a UI
    message via that context and raises NoSessionContext off the main thread.

    Loads from a locally bundled copy (assets/models/embedding, produced
    by scripts/download_models.py) if present, so there's no Hugging Face
    Hub network call at all on cold start. Falls back to the Hub model
    name otherwise (e.g. before you've run the download script).
    """
    local_path = Path(__file__).resolve().parent.parent.parent / "assets" / "models" / "embedding"
    model = str(local_path) if local_path.exists() else os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    return HuggingFaceEmbeddings(model_name=model)


@st.cache_resource
def get_chroma_client() -> chromadb.ClientAPI:
    """In-memory Chroma client, cached per process (one instance for the
    life of the Streamlit server process).

    Deliberately NOT a PersistentClient: this app's actual requirement is
    "build fresh each time I open the site, discard when I close it" — no
    workflow needs the KB to survive a restart. An in-memory client removes
    all disk I/O from every build (no writing embeddings/segments to disk,
    no delete_collection()/get_or_create_collection() disk teardown-rebuild
    in reset_collections()), which directly speeds up both first builds and
    rebuilds. Note this still lives as long as the Streamlit *process* does —
    closing a browser tab alone won't clear it if the server process is still
    running, but stopping/restarting the process (the situation "closing the
    website" maps to for local dev) does.
    """
    return chromadb.EphemeralClient(
        settings=Settings(anonymized_telemetry=False),
    )


def get_text_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
        separators=["\n## ", "\n### ", "\n\n", "\n", " "],
    )


def reset_collections() -> None:
    """Drop and recreate both collections."""
    client = get_chroma_client()
    for name in (DOCS_COLLECTION, GITHUB_COLLECTION):
        try:
            client.delete_collection(name)
        except (ValueError, chromadb.errors.NotFoundError):
            pass
    from src.utils.retrieval import invalidate_retrieval_cache  # local import: avoid circular import

    invalidate_retrieval_cache()


def embed_texts(texts: list[str]) -> list[list[float]]:
    return get_embeddings().embed_documents(texts)


def add_to_collection(
    collection_name: str,
    ids: list[str],
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> None:
    client = get_chroma_client()
    collection = client.get_or_create_collection(collection_name)
    embeddings = embed_texts(documents)
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )
    from src.utils.retrieval import invalidate_retrieval_cache  # local import: avoid circular import

    invalidate_retrieval_cache(collection_name)


def query_collection(
    collection_name: str,
    query: str,
    n_results: int = 5,
    where: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
    except (ValueError, chromadb.errors.NotFoundError):
        return []

    query_embedding = get_embeddings().embed_query(query)
    kwargs: dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)
    items: list[dict[str, Any]] = []
    if not results["ids"] or not results["ids"][0]:
        return items

    for i, doc_id in enumerate(results["ids"][0]):
        distance = results["distances"][0][i] if results["distances"] else 1.0
        # Chroma returns L2 distance; convert to similarity in [0,1]
        similarity = max(0.0, 1.0 - distance)
        items.append(
            {
                "id": doc_id,
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "vector_score": similarity,
            }
        )
    return items


def collection_stats() -> dict[str, int]:
    client = get_chroma_client()
    stats: dict[str, int] = {"docs_chunks": 0, "github_items": 0}
    for name, key in (
        (DOCS_COLLECTION, "docs_chunks"),
        (GITHUB_COLLECTION, "github_items"),
    ):
        try:
            col = client.get_collection(name)
            stats[key] = col.count()
        except (ValueError, chromadb.errors.NotFoundError):
            stats[key] = 0
    return stats
