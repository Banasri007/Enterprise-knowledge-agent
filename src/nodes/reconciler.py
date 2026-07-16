"""Reconciliation / critic node — detect conflicts and assess evidence sufficiency."""

from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from src.models.schemas import ConflictDetail, EvidenceItem
from src.state import AgentState
from src.utils.llm import get_llm

RECONCILE_SYSTEM = """You are a critic that compares documentation evidence vs GitHub change history.
Your job:
1. Determine if sources AGREE or CONFLICT on the answer
2. If they conflict, describe BOTH perspectives explicitly — never silently pick one
3. Assess if total evidence is SUFFICIENT to answer confidently

Respond ONLY with JSON:
{
  "conflict_detected": true/false,
  "conflicts": [
    {
      "topic": "what they disagree about",
      "docs_perspective": "what docs say",
      "github_perspective": "what commits/PRs show",
      "docs_citations": ["doc-name §section"],
      "github_citations": ["commit abc1234", "PR #42"],
      "resolution_note": "recommend trusting GitHub for current state, docs for intent"
    }
  ],
  "evidence_sufficient": true/false,
  "reconciliation_notes": "summary of agreement/disagreement"
}
"""


def _format_evidence(items: list[EvidenceItem], source: str) -> str:
    filtered = [e for e in items if e.source_type == source]
    if not filtered:
        return f"No {source} evidence."
    return "\n".join(
        f"- [{e.citation_label}] (score={e.composite_score:.2f}): {e.content[:300]}"
        for e in filtered
    )


def reconciler_node(state: AgentState) -> dict:
    """Compare sources, detect conflicts, judge evidence sufficiency."""
    question = state.get("rewritten_query") or state["question"]
    ranked = state.get("ranked_evidence", [])
    route = state.get("route", "both")

    docs_text = _format_evidence(ranked, "docs")
    github_text = _format_evidence(ranked, "github")

    llm = get_llm(fast=True)
    response = llm.invoke(
        [
            SystemMessage(content=RECONCILE_SYSTEM),
            HumanMessage(
                content=(
                    f"Question: {question}\n"
                    f"Route: {route}\n\n"
                    f"DOCS EVIDENCE:\n{docs_text}\n\n"
                    f"GITHUB EVIDENCE:\n{github_text}"
                )
            ),
        ]
    )
    content = response.content if isinstance(response.content, str) else str(response.content)

    conflict_detected = False
    conflicts: list[ConflictDetail] = []
    evidence_sufficient = len(ranked) >= 2
    notes = "Evidence reviewed."

    try:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            conflict_detected = bool(parsed.get("conflict_detected"))
            evidence_sufficient = bool(parsed.get("evidence_sufficient", evidence_sufficient))
            notes = parsed.get("reconciliation_notes", notes)
            for c in parsed.get("conflicts", []):
                conflicts.append(
                    ConflictDetail(
                        topic=c.get("topic", ""),
                        docs_perspective=c.get("docs_perspective", ""),
                        github_perspective=c.get("github_perspective", ""),
                        docs_citations=c.get("docs_citations", []),
                        github_citations=c.get("github_citations", []),
                        resolution_note=c.get("resolution_note", ""),
                    )
                )
    except (json.JSONDecodeError, AttributeError):
        pass

    # Boost sufficiency check using source grades
    docs_grade = state.get("docs_grade")
    github_grade = state.get("github_grade")
    if route == "docs" and docs_grade and docs_grade.confidence >= 0.6:
        evidence_sufficient = True
    elif route == "github" and github_grade and github_grade.confidence >= 0.6:
        evidence_sufficient = True
    elif route == "both":
        docs_ok = docs_grade and docs_grade.is_grounded and docs_grade.confidence >= 0.5
        github_ok = github_grade and github_grade.is_grounded and github_grade.confidence >= 0.5
        if docs_ok or github_ok:
            evidence_sufficient = evidence_sufficient or (docs_ok and github_ok)

    return {
        "conflict_detected": conflict_detected,
        "conflict_details": conflicts,
        "reconciliation_notes": notes,
        "evidence_sufficient": evidence_sufficient,
    }
