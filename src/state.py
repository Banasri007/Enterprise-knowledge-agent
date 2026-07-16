"""LangGraph shared state schema."""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from src.models.schemas import (
    Citation,
    ConflictDetail,
    EvidenceItem,
    ReasoningTrace,
    SourceGrade,
)


def _merge_evidence(
    left: list[EvidenceItem], right: list[EvidenceItem]
) -> list[EvidenceItem]:
    """Merge evidence lists from parallel agent fan-in."""
    return left + right


class AgentState(TypedDict, total=False):
    """Shared state passed between all LangGraph nodes."""

    # --- Input ---
    question: str
    repo_url: str

    # --- Planner output ---
    route: Literal["docs", "github", "both"]
    route_reason: str

    # --- Per-source retrieval (parallel fan-in via reducer) ---
    docs_evidence: Annotated[list[EvidenceItem], _merge_evidence]
    github_evidence: Annotated[list[EvidenceItem], _merge_evidence]

    # --- Per-source grounding grades ---
    docs_grade: SourceGrade | None
    github_grade: SourceGrade | None

    # --- Evidence ranker output ---
    ranked_evidence: list[EvidenceItem]

    # --- Reconciliation / critic ---
    conflict_detected: bool
    conflict_details: list[ConflictDetail]
    reconciliation_notes: str
    evidence_sufficient: bool

    # --- Self-correction loop ---
    retry_count: int
    max_retries: int
    self_correction_triggered: bool
    self_correction_notes: str
    original_query: str
    rewritten_query: str

    # --- Final output ---
    final_answer: str
    citations: list[Citation]
    reasoning_trace: ReasoningTrace

    # --- Internal routing flags (not shown in UI) ---
    _active_source: Literal["docs", "github", "none"]
