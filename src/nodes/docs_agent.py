"""Docs retrieval agent with grounding/relevance check."""

from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from src.models.schemas import EvidenceItem, SourceGrade
from src.state import AgentState
from src.utils.llm import get_llm
from src.utils.retrieval import hybrid_query
from src.utils.vector_store import DOCS_COLLECTION

GROUNDING_SYSTEM = """You grade whether retrieved documentation evidence can answer the question.
Respond ONLY with JSON:
{
  "is_grounded": true/false,
  "is_relevant": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation",
  "item_scores": [{"index": 0, "grounding": 0.0-1.0, "relevance": 0.0-1.0}]
}
"""


def _grade_evidence(question: str, items: list[EvidenceItem]) -> SourceGrade:
    if not items:
        return SourceGrade(
            source_type="docs",
            is_grounded=False,
            is_relevant=False,
            confidence=0.0,
            reasoning="No documentation chunks retrieved.",
            evidence_count=0,
        )

    evidence_text = "\n\n".join(
        f"[{i}] ({e.citation_label}): {e.content[:500]}"
        for i, e in enumerate(items)
    )
    llm = get_llm()
    response = llm.invoke(
        [
            SystemMessage(content=GROUNDING_SYSTEM),
            HumanMessage(
                content=f"Question: {question}\n\nEvidence:\n{evidence_text}"
            ),
        ]
    )
    content = response.content if isinstance(response.content, str) else str(response.content)

    grade = SourceGrade(
        source_type="docs",
        is_grounded=False,
        is_relevant=False,
        confidence=0.3,
        reasoning="Could not parse grading response.",
        evidence_count=len(items),
    )
    try:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            grade = SourceGrade(
                source_type="docs",
                is_grounded=bool(parsed.get("is_grounded")),
                is_relevant=bool(parsed.get("is_relevant")),
                confidence=float(parsed.get("confidence", 0.3)),
                reasoning=parsed.get("reasoning", ""),
                evidence_count=len(items),
            )
            for score in parsed.get("item_scores", []):
                idx = score.get("index", -1)
                if 0 <= idx < len(items):
                    items[idx].grounding_score = float(score.get("grounding", 0.0))
                    items[idx].relevance_score = float(score.get("relevance", 0.0))
    except (json.JSONDecodeError, ValueError, AttributeError):
        pass

    return grade


def docs_agent_node(state: AgentState) -> dict:
    """Retrieve from docs corpus and grade grounding."""
    question = state.get("rewritten_query") or state["question"]
    raw = hybrid_query(DOCS_COLLECTION, question, n_results=5)

    evidence: list[EvidenceItem] = []
    for item in raw:
        evidence.append(
            EvidenceItem(
                source_type="docs",
                content=item["content"],
                metadata=item["metadata"],
                vector_score=item["vector_score"],
            )
        )

    grade = _grade_evidence(question, evidence)

    # Filter out poorly grounded items
    filtered = [
        e
        for e in evidence
        if e.grounding_score >= 0.3 or e.vector_score >= 0.5
    ] if grade.is_grounded else []

    return {
        "docs_evidence": filtered or evidence,
        "docs_grade": grade,
    }
