"""Dispatcher node — always fans out to both docs and GitHub sources.

Previously this made an LLM call to decide which source(s) to query.
That routing step was cut: it added latency/cost per question, and worse,
a wrong guess silently dropped the correct source's evidence entirely
(e.g. "what is X" questions were routed to docs-only, even when the
answer only lived in the GitHub repo's README). Since we only have two
collections, always searching both and letting the evidence ranker sort
out what's actually relevant is simpler, faster, and strictly more
correct than trying to predict the right source in advance.
"""

from __future__ import annotations

from src.state import AgentState


def planner_node(state: AgentState) -> dict:
    """No-op dispatcher: always search both sources."""
    return {
        "route": "both",
        "route_reason": "Always searching docs + GitHub together (no pre-filtering).",
    }