"""LangGraph StateGraph — planner routing, parallel fan-out, self-correction loop."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from src.nodes.answer_generator import answer_generator_node
from src.nodes.docs_agent import docs_agent_node
from src.nodes.evidence_ranker import evidence_ranker_node
from src.nodes.github_agent import github_agent_node
from src.nodes.planner import planner_node
from src.nodes.reconciler import reconciler_node
from src.nodes.self_corrector import self_corrector_node
from src.state import AgentState

MAX_RETRIES = 2


def _route_to_agents(state: AgentState) -> str | list[Send]:
    """Conditional edge: planner → docs / github / both (parallel)."""
    route = state.get("route", "both")
    if route == "docs":
        return "docs_agent"
    if route == "github":
        return "github_agent"
    # Parallel fan-out via Send
    return [
        Send("docs_agent", state),
        Send("github_agent", state),
    ]


def _after_self_correct(state: AgentState) -> str:
    """Loop back to planner with rewritten query."""
    return "planner"


def _after_reconciler(state: AgentState) -> str:
    """Conditional edge: sufficient evidence → answer, else self-correct (bounded)."""
    if state.get("evidence_sufficient"):
        return "answer_generator"
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", MAX_RETRIES)
    if retry_count >= max_retries:
        return "answer_generator"
    return "self_corrector"


def build_graph() -> StateGraph:
    """Construct and compile the enterprise knowledge agent graph."""
    graph = StateGraph(AgentState)

    # --- Register nodes ---
    graph.add_node("planner", planner_node)
    graph.add_node("docs_agent", docs_agent_node)
    graph.add_node("github_agent", github_agent_node)
    graph.add_node("evidence_ranker", evidence_ranker_node)
    graph.add_node("reconciler", reconciler_node)
    graph.add_node("self_corrector", self_corrector_node)
    graph.add_node("answer_generator", answer_generator_node)

    # --- Edges ---
    graph.add_edge(START, "planner")

    # Planner → conditional routing (single or parallel fan-out)
    graph.add_conditional_edges("planner", _route_to_agents)

    # Fan-in: both agents converge on evidence ranker
    graph.add_edge("docs_agent", "evidence_ranker")
    graph.add_edge("github_agent", "evidence_ranker")

    graph.add_edge("evidence_ranker", "reconciler")

    # Reconciler → answer OR self-correction loop (bounded)
    graph.add_conditional_edges("reconciler", _after_reconciler)

    # Self-correction cyclical edge → back to planner
    graph.add_conditional_edges("self_corrector", _after_self_correct)

    graph.add_edge("answer_generator", END)

    return graph.compile()


def run_agent(question: str, repo_url: str = "") -> AgentState:
    """Execute the full agent pipeline for a single question."""
    app = build_graph()
    initial: AgentState = {
        "question": question,
        "repo_url": repo_url,
        "retry_count": 0,
        "max_retries": MAX_RETRIES,
        "self_correction_triggered": False,
        "conflict_detected": False,
        "conflict_details": [],
        "docs_evidence": [],
        "github_evidence": [],
        "ranked_evidence": [],
        "citations": [],
    }
    return app.invoke(initial)