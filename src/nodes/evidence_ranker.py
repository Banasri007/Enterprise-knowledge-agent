"""Evidence ranker — recency + authority + relevance, not just vector similarity."""

from __future__ import annotations

from src.models.schemas import EvidenceItem
from src.state import AgentState

# Authority weights by source type and item type
AUTHORITY_WEIGHTS = {
    ("docs", "doc"): 0.85,
    ("github", "pr"): 0.90,
    ("github", "commit"): 0.75,
}

# Composite score weights
W_RELEVANCE = 0.35
W_GROUNDING = 0.25
W_RECENCY = 0.25
W_AUTHORITY = 0.15


def _authority_score(item: EvidenceItem) -> float:
    if item.source_type == "docs":
        return AUTHORITY_WEIGHTS[("docs", "doc")]
    item_type = item.metadata.get("item_type", "commit")
    return AUTHORITY_WEIGHTS.get(("github", item_type), 0.7)


def _composite_score(item: EvidenceItem) -> float:
    relevance = item.relevance_score or item.vector_score
    grounding = item.grounding_score or (item.vector_score * 0.8)
    recency = item.recency_score if item.source_type == "github" else 0.6
    authority = _authority_score(item)

    return (
        W_RELEVANCE * relevance
        + W_GROUNDING * grounding
        + W_RECENCY * recency
        + W_AUTHORITY * authority
    )


def evidence_ranker_node(state: AgentState) -> dict:
    """Merge and rank evidence from all active sources."""
    route = state.get("route", "both")
    all_evidence: list[EvidenceItem] = []

    if route in ("docs", "both"):
        all_evidence.extend(state.get("docs_evidence", []))
    if route in ("github", "both"):
        all_evidence.extend(state.get("github_evidence", []))

    for item in all_evidence:
        item.authority_score = _authority_score(item)
        if item.source_type == "docs" and item.recency_score == 0.0:
            item.recency_score = 0.5  # docs have no timestamp; neutral recency
        item.composite_score = _composite_score(item)

    ranked = sorted(all_evidence, key=lambda e: e.composite_score, reverse=True)
    return {"ranked_evidence": ranked[:8]}
