"""Final answer generator with citations."""

from __future__ import annotations

import re
from collections import OrderedDict

from langchain_core.messages import HumanMessage, SystemMessage

from src.models.schemas import Citation, EvidenceItem, ReasoningTrace
from src.state import AgentState
from src.utils.llm import get_llm

# Safety net for the "no inline bracket citations" instruction in
# ANSWER_SYSTEM: LLM instruction-following on formatting rules isn't 100%
# reliable, so enforce it in code too rather than relying on the prompt
# alone. Matches bracket spans that look like citations -- containing a
# file extension, a section marker (§), "commit", "PR #", "Issue #", or a
# path separator -- so we don't accidentally eat an unrelated "[note]" the
# model writes for some other reason.
_INLINE_CITATION_RE = re.compile(
    r"\s*\[[^\[\]]{0,120}"
    r"(?:\.pdf|\.md|\.txt|\.py|\.js|\.ts|§|commit\s|PR\s?#|Issue\s?#|/)"
    r"[^\[\]]{0,120}\]",
    re.IGNORECASE,
)


def _strip_inline_citations(text: str) -> str:
    return _INLINE_CITATION_RE.sub("", text)


ANSWER_SYSTEM = """You are an enterprise knowledge agent. Answer the user's question using ONLY the provided evidence.

OUTPUT FORMAT — this is mandatory, not optional:
- Structure the answer into clearly labeled sections by source, in this order: "### From Documentation" first (with one sub-bullet per distinct document, headed by its document name in bold, e.g. "**authentication.md**"), then "### From GitHub History" (commits/PRs together, no need to sub-group by individual commit).
- Within each document's sub-section, synthesize the relevant content into a short answer for that document. Do NOT add inline bracket citations like "[doc-name §section]" in the middle of sentences — the bold document name in the bullet heading already identifies the source, repeating it inline is redundant clutter.
- For GitHub History points, likewise write the point in plain prose with no inline brackets — instead end that point with its own line: "Source: <the specific commit SHA, PR #, or file path>". One Source line per distinct GitHub item referenced, not one per sentence.
- Include a section (or a specific document's sub-bullet) ONLY if that source actually contains evidence that is relevant and contributes to answering the question. If a source was retrieved but is not actually relevant to this specific question, silently drop it — do not create an empty section for it and do not mention it at all.
- If only one source (or only one document) has the answer, output ONLY that section. Do not add sentences like "GitHub history does not mention this" or "this was not found in the documentation" — the reader only wants the answer, not an inventory of what's missing. (The full retrieval detail is available separately in a reasoning panel if the reader wants it — your job here is only the answer.)
- Exception: if two sources genuinely disagree on a factual point (not just "one is silent and one has info", but both have relevant, conflicting information), present both perspectives explicitly rather than picking one — this is a real conflict, not a missing-source case, and matters more than section neatness.
- Prefer recent GitHub evidence for "current state" questions; prefer docs for "how it should work"/intended-design questions.
- If NO evidence anywhere is relevant, say so honestly in one line rather than fabricating sections.
- Be concise but thorough within each section.
"""


def _group_evidence(items: list[EvidenceItem]) -> tuple[OrderedDict[str, list[EvidenceItem]], list[EvidenceItem]]:
    """Split evidence into per-document groups (docs source) and a flat list (github source),
    preserving the ranked order items already arrived in."""
    docs_by_name: OrderedDict[str, list[EvidenceItem]] = OrderedDict()
    github_items: list[EvidenceItem] = []
    for e in items:
        if e.source_type == "docs":
            doc_name = e.metadata.get("doc_name", "unknown-doc")
            docs_by_name.setdefault(doc_name, []).append(e)
        else:
            github_items.append(e)
    return docs_by_name, github_items


def _build_evidence_block(items: list[EvidenceItem]) -> str:
    if not items:
        return "No evidence available."

    docs_by_name, github_items = _group_evidence(items)
    sections = []

    if docs_by_name:
        doc_lines = ["DOCS EVIDENCE (grouped by document — mirror this grouping in your answer):"]
        for doc_name, doc_items in docs_by_name.items():
            doc_lines.append(f"\n--- Document: {doc_name} ---")
            for e in doc_items:
                url_note = f" ({e.citation_url})" if e.citation_url else ""
                doc_lines.append(
                    f"[{e.citation_label}]{url_note} (score={e.composite_score:.2f}):\n{e.content[:600]}"
                )
        sections.append("\n".join(doc_lines))

    if github_items:
        gh_lines = ["GITHUB EVIDENCE (commits/PRs):"]
        for e in github_items:
            url_note = f" ({e.citation_url})" if e.citation_url else ""
            gh_lines.append(
                f"[{e.citation_label}]{url_note} (score={e.composite_score:.2f}):\n{e.content[:600]}"
            )
        sections.append("\n".join(gh_lines))

    return "\n\n".join(sections)


def answer_generator_node(state: AgentState) -> dict:
    """Produce the final answer with citations."""
    question = state["question"]
    ranked = state.get("ranked_evidence", [])
    conflicts = state.get("conflict_details", [])
    reconciliation = state.get("reconciliation_notes", "")

    conflict_block = ""
    if conflicts:
        conflict_block = "\n\nGENUINE CONFLICTS DETECTED (both sources have relevant but disagreeing info — present both perspectives for these specific points):\n" + "\n".join(
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
    answer = _strip_inline_citations(answer)

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
