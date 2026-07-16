"""Self-correction node — rewrite query when evidence is too thin."""

from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from src.state import AgentState
from src.utils.llm import get_llm

REWRITE_SYSTEM = """The initial retrieval did not find sufficient evidence to answer confidently.
Rewrite the user's question to improve retrieval. Strategies:
- Add specific technical terms from the domain
- Decompose a complex question into a more targeted sub-question
- Rephrase to match how docs/commits are written (e.g., "OAuth2 migration" → "replace OAuth with API key authentication")

Respond ONLY with JSON:
{
  "rewritten_query": "the improved query",
  "strategy": "brief note on what you changed"
}
"""


def self_corrector_node(state: AgentState) -> dict:
    """Rewrite the query for a bounded retry."""
    question = state.get("rewritten_query") or state["question"]
    original = state.get("original_query") or state["question"]
    retry_count = state.get("retry_count", 0)

    docs_grade = state.get("docs_grade")
    github_grade = state.get("github_grade")

    grade_summary = (
        f"Docs grade: {docs_grade.confidence if docs_grade else 'N/A'}, "
        f"GitHub grade: {github_grade.confidence if github_grade else 'N/A'}"
    )

    llm = get_llm(temperature=0.3)
    response = llm.invoke(
        [
            SystemMessage(content=REWRITE_SYSTEM),
            HumanMessage(
                content=(
                    f"Original question: {original}\n"
                    f"Current query (attempt {retry_count + 1}): {question}\n"
                    f"Grades: {grade_summary}\n"
                    f"Reconciliation: {state.get('reconciliation_notes', '')}"
                )
            ),
        ]
    )
    content = response.content if isinstance(response.content, str) else str(response.content)

    rewritten = question
    strategy = "Rephrased for better retrieval coverage."
    try:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            rewritten = parsed.get("rewritten_query", rewritten)
            strategy = parsed.get("strategy", strategy)
    except (json.JSONDecodeError, AttributeError):
        pass

    return {
        "rewritten_query": rewritten,
        "original_query": original,
        "retry_count": retry_count + 1,
        "self_correction_triggered": True,
        "self_correction_notes": (
            f"Initial retrieval was weak — rewrote query and retried. {strategy}"
        ),
        # Clear prior retrieval for fresh pass
        "docs_evidence": [],
        "github_evidence": [],
        "ranked_evidence": [],
    }
