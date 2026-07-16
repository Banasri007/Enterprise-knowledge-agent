"""Embedding and vector store utilities using ChromaDB."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHROMA_DIR = Path(".chroma_data")
DOCS_COLLECTION = "docs_corpus"
GITHUB_COLLECTION = "github_history"


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """Local sentence-transformer embeddings (Groq has no embedding API).

    Cached so the model is loaded from disk once per process instead of
    on every single embed call — this was the main ingestion slowdown.
    """
    model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    return HuggingFaceEmbeddings(model_name=model)


@lru_cache(maxsize=1)
def get_chroma_client() -> chromadb.ClientAPI:
    """Persistent local Chroma client, cached per process."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(CHROMA_DIR),
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
