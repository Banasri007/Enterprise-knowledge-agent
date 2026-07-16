"""Advanced retrieval pipeline.

Stages, in order:
  1. Hybrid retrieval — EnsembleRetriever combining a Chroma vector
     retriever (MMR search, for diverse semantic matches) with a BM25
     keyword retriever (for exact terms embeddings tend to miss, e.g.
     identifiers like CUSTSRCH or file paths), weighted 0.7 vector /
     0.3 BM25.
  2. MultiQueryRetriever wraps the hybrid retriever — the LLM generates
     a few paraphrased variants of the question and each is retrieved
     against, catching phrasing mismatches between the question and the
     source text.
  3. Cross-encoder reranking — a dedicated stage (not just relying on
     the retriever's own scoring) that jointly scores (query, doc)
     pairs, which is far more accurate than embedding similarity alone
     for the final top-k selection.
  4. Retrieval-level LRU cache — repeated/similar questions within a
     session skip the whole pipeline above.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from functools import lru_cache
from typing import Any

from langchain_chroma import Chroma
from langchain_classic.retrievers import EnsembleRetriever
from langchain_classic.retrievers.multi_query import MultiQueryRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder

from src.utils.llm import get_llm
from src.utils.vector_store import get_chroma_client, get_embeddings

RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
VECTOR_WEIGHT = 0.7
BM25_WEIGHT = 0.3
MMR_K = 10
MMR_FETCH_K = 20
MMR_LAMBDA = 0.5
BM25_K = 10
CACHE_MAXSIZE = 128

# Query-result cache: query+collection -> final reranked results.
# Plain dict + manual ordering (not functools.lru_cache) because the
# cache must be invalidated on ingestion writes, which lru_cache doesn't
# support per-key.
_retrieval_cache: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()

# Bumped per collection whenever new data is ingested, so the BM25
# retriever (which snapshots all documents at build time) gets rebuilt
# instead of silently going stale.
_collection_versions: dict[str, int] = {}


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoder:
    """Cross-encoder reranker model, loaded once per process."""
    return CrossEncoder(RERANK_MODEL)


@lru_cache(maxsize=8)
def _get_vectorstore(collection_name: str) -> Chroma:
    return Chroma(
        client=get_chroma_client(),
        collection_name=collection_name,
        embedding_function=get_embeddings(),
    )


@lru_cache(maxsize=16)
def _get_bm25_retriever(collection_name: str, version: int) -> BM25Retriever | None:
    """Snapshot-built BM25 index. `version` is part of the cache key
    purely so invalidate_retrieval_cache() can force a rebuild by
    bumping it — the value itself isn't otherwise used."""
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
    except Exception:
        return None

    data = collection.get(include=["documents", "metadatas"])
    texts = data.get("documents") or []
    if not texts:
        return None
    metadatas = data.get("metadatas") or [{}] * len(texts)
    ids = data.get("ids") or [str(i) for i in range(len(texts))]

    documents = [
        Document(page_content=text, metadata={**(meta or {}), "_id": doc_id})
        for text, meta, doc_id in zip(texts, metadatas, ids)
    ]
    retriever = BM25Retriever.from_documents(documents)
    retriever.k = BM25_K
    return retriever


def invalidate_retrieval_cache(collection_name: str | None = None) -> None:
    """Call after any ingestion write. Clears the result cache and
    forces the BM25 index to rebuild from fresh data on next query."""
    if collection_name:
        _collection_versions[collection_name] = _collection_versions.get(collection_name, 0) + 1
    else:
        for name in list(_collection_versions) or [None]:
            if name:
                _collection_versions[name] = _collection_versions.get(name, 0) + 1
    _retrieval_cache.clear()


def _build_retriever(collection_name: str):
    vector_retriever = _get_vectorstore(collection_name).as_retriever(
        search_type="mmr",
        search_kwargs={"k": MMR_K, "fetch_k": MMR_FETCH_K, "lambda_mult": MMR_LAMBDA},
    )
    version = _collection_versions.get(collection_name, 0)
    bm25_retriever = _get_bm25_retriever(collection_name, version)

    hybrid = (
        EnsembleRetriever(
            retrievers=[vector_retriever, bm25_retriever],
            weights=[VECTOR_WEIGHT, BM25_WEIGHT],
        )
        if bm25_retriever is not None
        else vector_retriever  # no ingested data yet for BM25 to index
    )
    return MultiQueryRetriever.from_llm(retriever=hybrid, llm=get_llm())


def _rerank(query: str, docs: list[Document], top_k: int) -> list[tuple[Document, float]]:
    if not docs:
        return []
    pairs = [[query, d.page_content] for d in docs]
    scores = get_reranker().predict(pairs)
    scored = list(zip(docs, (float(s) for s in scores)))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]


def _cache_key(collection_name: str, query: str, n_results: int) -> str:
    raw = f"{collection_name}::{n_results}::{query.strip().lower()}"
    return hashlib.sha1(raw.encode()).hexdigest()


def hybrid_query(collection_name: str, query: str, n_results: int = 5) -> list[dict[str, Any]]:
    """Full retrieval pipeline: hybrid (vector+BM25) -> multi-query
    expansion -> cross-encoder rerank -> cache. Same return shape as
    the old query_collection() so callers don't need to change."""
    key = _cache_key(collection_name, query, n_results)
    if key in _retrieval_cache:
        _retrieval_cache.move_to_end(key)
        return _retrieval_cache[key]

    try:
        retriever = _build_retriever(collection_name)
        candidates = retriever.invoke(query)
    except Exception:
        candidates = []

    # MultiQuery + Ensemble commonly return overlapping docs; dedupe by content.
    seen: set[str] = set()
    unique_docs: list[Document] = []
    for doc in candidates:
        content_hash = hashlib.sha1(doc.page_content.encode()).hexdigest()
        if content_hash not in seen:
            seen.add(content_hash)
            unique_docs.append(doc)

    reranked = _rerank(query, unique_docs, top_k=n_results)

    results: list[dict[str, Any]] = []
    for doc, score in reranked:
        meta = dict(doc.metadata or {})
        doc_id = meta.pop("_id", "")
        # ms-marco cross-encoder logits roughly span [-10, 10]; squash to [0,1]
        # for compatibility with existing downstream score thresholds.
        normalized = max(0.0, min(1.0, (score + 10.0) / 20.0))
        results.append(
            {
                "id": doc_id,
                "content": doc.page_content,
                "metadata": meta,
                "vector_score": normalized,
                "rerank_score": score,
            }
        )

    _retrieval_cache[key] = results
    _retrieval_cache.move_to_end(key)
    if len(_retrieval_cache) > CACHE_MAXSIZE:
        _retrieval_cache.popitem(last=False)  # evict least-recently-used

    return results
