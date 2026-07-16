"""Streamlit UI — Setup screen + Chat with reasoning panel."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

CORPUS_DIR = Path(__file__).parent / "docs" / "corpus"
SAMPLE_REPO_URL = "https://github.com/acme-corp/nexus-integration-hub"

st.set_page_config(
    page_title="Enterprise Knowledge Agent",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Session state defaults ---
if "kb_built" not in st.session_state:
    st.session_state.kb_built = False
if "kb_stats" not in st.session_state:
    st.session_state.kb_stats = {}
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_reasoning" not in st.session_state:
    st.session_state.last_reasoning = None


def _check_api_key() -> bool:
    key = os.getenv("GROQ_API_KEY", "")
    return bool(key and not key.startswith("gsk_your"))


# --- Sidebar navigation ---
st.sidebar.title("Enterprise Knowledge Agent")
st.sidebar.caption("Acme Corp · Nexus Integration Hub demo")
page = st.sidebar.radio("Navigate", ["Setup", "Chat"], index=0 if not st.session_state.kb_built else 1)

st.sidebar.markdown("---")
st.sidebar.markdown("**Demo test questions:**")
st.sidebar.code("How does API authentication work?", language=None)
st.sidebar.code("When was API key auth introduced?", language=None)
st.sidebar.code("What auth method does the system currently use?", language=None)

if not _check_api_key():
    st.sidebar.warning("Set GROQ_API_KEY in `.env` or Streamlit secrets.")


# ====================================================================
# SCREEN 1 — Setup / Knowledge Base Builder
# ====================================================================
if page == "Setup":
    st.title("Knowledge Base Builder")
    st.markdown(
        "Index an **enterprise PDF documentation corpus** and **GitHub commit/PR history** "
        "for the fictional **Acme Corp Nexus Integration Hub** to power the multi-source RAG agent."
    )

    use_sample = st.checkbox(
        "Use bundled Acme Corp sample data (recommended for demo)",
        value=True,
        help=(
            "Loads 5 PDF docs + 8 synthetic GitHub items from "
            f"`{SAMPLE_REPO_URL}` designed to produce a docs/GitHub auth conflict."
        ),
    )

    repo_url = st.text_input(
        "GitHub Repo URL (public)",
        value=SAMPLE_REPO_URL if not use_sample else "",
        placeholder=SAMPLE_REPO_URL,
        disabled=use_sample,
        help="For live mode, use any public repo. Sample mode uses mock Acme Corp commit/PR data.",
    )

    uploaded_files = st.file_uploader(
        "Upload documentation files (.pdf / .md / .txt)",
        type=["pdf", "md", "txt"],
        accept_multiple_files=True,
        disabled=use_sample,
    )

    if st.button("Build Knowledge Base", type="primary", use_container_width=True):
        if not _check_api_key():
            st.error("GROQ_API_KEY is required. Copy `.env.example` to `.env` and add your key.")
            st.stop()

        from src.ingestion.docs_ingestion import (
            index_doc_chunks,
            ingest_doc_bytes,
            ingest_docs_from_directory,
        )
        from src.ingestion.github_ingestion import fetch_github_history, index_github_items
        from src.ingestion.sample_data import load_sample_github_items
        from src.utils.vector_store import reset_collections

        progress = st.progress(0, text="Resetting vector store...")
        reset_collections()
        progress.progress(10, text="Processing documents...")

        doc_chunks = []
        doc_file_count = 0

        if use_sample:
            if not CORPUS_DIR.exists() or not list(CORPUS_DIR.glob("*.pdf")):
                from scripts.generate_corpus_pdfs import main as generate_pdfs

                generate_pdfs()
            doc_chunks = ingest_docs_from_directory(CORPUS_DIR)
            doc_file_count = len(list(CORPUS_DIR.glob("*.pdf")))
        elif uploaded_files:
            for f in uploaded_files:
                doc_chunks.extend(ingest_doc_bytes(f.name, f.read()))
                doc_file_count += 1
        else:
            st.error("Upload at least one doc file, or enable sample data.")
            st.stop()

        chunk_count = index_doc_chunks(doc_chunks)
        progress.progress(40, text="Fetching GitHub history...")

        github_items = []
        if use_sample:
            github_items = load_sample_github_items()
        elif repo_url:
            try:
                github_items = fetch_github_history(repo_url)
            except Exception as exc:
                st.error(f"GitHub fetch failed: {exc}")
                st.stop()
        else:
            st.error("Provide a GitHub repo URL, or enable sample data.")
            st.stop()

        github_count = index_github_items(github_items)
        progress.progress(90, text="Finalizing...")

        commit_count = sum(1 for i in github_items if i.item_type == "commit")
        pr_count = sum(1 for i in github_items if i.item_type == "pr")

        st.session_state.kb_built = True
        st.session_state.kb_stats = {
            "commits": commit_count,
            "prs": pr_count,
            "documents": doc_file_count,
            "chunks": chunk_count,
            "github_items": github_count,
            "repo_url": SAMPLE_REPO_URL if use_sample else repo_url,
        }
        progress.progress(100, text="Done!")
        st.success(
            f"Indexed **{commit_count}** commits, **{pr_count}** PRs, "
            f"**{doc_file_count}** PDF documents (**{chunk_count}** chunks)"
        )
        st.info("Switch to the **Chat** tab to start asking questions.")

    if st.session_state.kb_built:
        stats = st.session_state.kb_stats
        st.markdown("### Current Knowledge Base")
        if stats.get("repo_url"):
            st.caption(f"GitHub source: {stats['repo_url']}")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Commits", stats.get("commits", 0))
        col2.metric("PRs", stats.get("prs", 0))
        col3.metric("Documents", stats.get("documents", 0))
        col4.metric("Chunks", stats.get("chunks", 0))


# ====================================================================
# SCREEN 2 — Chat / Query Interface
# ====================================================================
elif page == "Chat":
    st.title("Chat")

    if not st.session_state.kb_built:
        st.warning("Build a knowledge base first on the **Setup** tab.")
        st.stop()

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Ask a question about Acme Corp Nexus Integration Hub...")

    if question:
        st.session_state.chat_history.append({"role": "user", "content": question})

        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Reasoning over knowledge sources..."):
                from src.graph import run_agent

                result = run_agent(question)
                answer = result.get("final_answer", "No answer generated.")
                st.markdown(answer)

                trace = result.get("reasoning_trace")
                if trace:
                    st.session_state.last_reasoning = trace

            st.session_state.chat_history.append({"role": "assistant", "content": answer})

    # --- Show Reasoning Panel ---
    trace = st.session_state.last_reasoning
    if trace:
        st.markdown("---")
        st.subheader("Show Reasoning")

        with st.expander("Planner Routing", expanded=True):
            route_icons = {"docs": "📄", "github": "🔀", "both": "📄+🔀"}
            icon = route_icons.get(trace.route, "")
            st.markdown(f"**Routed to:** {icon} `{trace.route}`")
            st.markdown(f"**Reason:** {trace.route_reason}")

        col_docs, col_gh = st.columns(2)
        with col_docs:
            with st.expander("Docs Agent — Grounding Grade"):
                if trace.docs_grade:
                    g = trace.docs_grade
                    st.markdown(f"Grounded: **{g.is_grounded}** | Relevant: **{g.is_relevant}**")
                    st.progress(g.confidence, text=f"Confidence: {g.confidence:.0%}")
                    st.caption(g.reasoning)
                else:
                    st.caption("Not queried.")

        with col_gh:
            with st.expander("GitHub Agent — Grounding Grade"):
                if trace.github_grade:
                    g = trace.github_grade
                    st.markdown(f"Grounded: **{g.is_grounded}** | Relevant: **{g.is_relevant}**")
                    st.progress(g.confidence, text=f"Confidence: {g.confidence:.0%}")
                    st.caption(g.reasoning)
                else:
                    st.caption("Not queried.")

        if trace.self_correction_triggered:
            with st.expander("Self-Correction Loop", expanded=True):
                st.warning(trace.self_correction_notes)
                st.markdown(f"**Original query:** {trace.original_query}")
                st.markdown(f"**Rewritten query:** {trace.rewritten_query}")
                st.markdown(f"**Retries:** {trace.retry_count}")

        if trace.conflict_detected and trace.conflict_details:
            st.markdown("### ⚠️ Conflict Detected")
            for conflict in trace.conflict_details:
                col_left, col_right = st.columns(2)
                with col_left:
                    st.markdown("**Documentation says:**")
                    st.info(conflict.docs_perspective)
                    if conflict.docs_citations:
                        st.caption("Citations: " + ", ".join(conflict.docs_citations))
                with col_right:
                    st.markdown("**GitHub history shows:**")
                    st.warning(conflict.github_perspective)
                    if conflict.github_citations:
                        st.caption("Citations: " + ", ".join(conflict.github_citations))
                if conflict.resolution_note:
                    st.markdown(f"*Resolution:* {conflict.resolution_note}")

        with st.expander("Ranked Evidence"):
            if trace.ranked_evidence:
                for ev in trace.ranked_evidence:
                    label = ev.citation_label
                    url = ev.citation_url
                    header = f"**{label}** — composite: {ev.composite_score:.2f}"
                    if url:
                        st.markdown(f"{header} — [link]({url})")
                    else:
                        st.markdown(header)
                    st.caption(
                        f"vector={ev.vector_score:.2f} | grounding={ev.grounding_score:.2f} | "
                        f"relevance={ev.relevance_score:.2f} | recency={ev.recency_score:.2f} | "
                        f"authority={ev.authority_score:.2f}"
                    )
                    st.text(ev.content[:300] + ("..." if len(ev.content) > 300 else ""))
                    st.divider()
            else:
                st.caption("No evidence ranked.")

        if trace.reconciliation_notes:
            with st.expander("Reconciliation Notes"):
                st.markdown(trace.reconciliation_notes)
