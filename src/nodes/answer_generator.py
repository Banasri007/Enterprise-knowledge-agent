"""Final answer generator with citations."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from src.models.schemas import Citation, EvidenceItem, ReasoningTrace
from src.state import AgentState
from src.utils.llm import get_llm

ANSWER_SYSTEM = """You are an enterprise knowledge agent. Answer the user's question using ONLY the provided evidence.
Rules:
1. Cite sources inline using [doc-name] or [commit SHA] or [PR #N] format
2. If sources conflict, present BOTH perspectives — do NOT silently pick one
3. Prefer recent GitHub evidence for "current state" questions; prefer docs for "how it should work"
4. If evidence is insufficient, say so honestly
5. Be concise but thorough
"""


def _build_evidence_block(items: list[EvidenceItem]) -> str:
    if not items:
        return "No evidence available."
    lines = []
    for e in items:
        url_note = f" ({e.citation_url})" if e.citation_url else ""
        lines.append(
            f"[{e.citation_label}]{url_note} (score={e.composite_score:.2f}):\n{e.content[:600]}"
        )
    return "\n\n".join(lines)


def answer_generator_node(state: AgentState) -> dict:
    """Produce the final answer with citations."""
    question = state["question"]
    ranked = state.get("ranked_evidence", [])
    conflicts = state.get("conflict_details", [])
    reconciliation = state.get("reconciliation_notes", "")

    conflict_block = ""
    if conflicts:
        conflict_block = "\n\nCONFLICTS DETECTED:\n" + "\n".join(
            f"- {c.topic}: Docs say '{c.docs_perspective}' vs GitHub shows '{c.github_perspective}'"
            for c in conflicts
        )

    llm = get_llm()
    response = llm.invoke(
        [
            SystemMessage(content=ANSWER_SYSTEM),
            HumanMessage(
                content=(
                    f"Question: {question}\n\n"
                    f"EVIDENCE:\n{_build_evidence_block(ranked)}\n\n"
                    f"RECONCILIATION: {reconciliation}"
                    f"{conflict_block}"
                )
            ),
        ]
    )
    answer = response.content if isinstance(response.content, str) else str(response.content)

    citations: list[Citation] = []
    for e in ranked[:5]:
        citations.append(
            Citation(
                label=e.citation_label,
                source_type=e.source_type,
                url=e.citation_url,
                excerpt=e.content[:200],
            )
        )

    trace = ReasoningTrace(
        route=state.get("route", "both"),
        route_reason=state.get("route_reason", ""),
        docs_grade=state.get("docs_grade"),
        github_grade=state.get("github_grade"),
        ranked_evidence=ranked,
        conflict_detected=state.get("conflict_detected", False),
        conflict_details=conflicts,
        reconciliation_notes=reconciliation,
        self_correction_triggered=state.get("self_correction_triggered", False),
        self_correction_notes=state.get("self_correction_notes", ""),
        original_query=state.get("original_query", question),
        rewritten_query=state.get("rewritten_query", ""),
        retry_count=state.get("retry_count", 0),
    )

    return {
        "final_answer": answer,
        "citations": citations,
        "reasoning_trace": trace,
    }
