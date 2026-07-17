"""Streamlit UI — Setup screen + Chat with reasoning panel."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

CORPUS_DIR = Path(__file__).parent / "docs" / "corpus"
SAMPLE_REPO_URL = "https://github.com/acme-corp/nexus-integration-hub"

# Visual language: two accent colors carry meaning throughout the app —
# indigo always means "from documentation", copper always means "from
# GitHub history". This isn't decoration, it's the same distinction the
# agent itself reasons about, made visible.
INDIGO = "#7C8CFF"
COPPER = "#E8A15C"

st.set_page_config(
    page_title="Enterprise Knowledge Agent",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
        --bg-deep: #0A0E1A;
        --bg-surface: #10162A;
        --bg-surface-2: #161D36;
        --indigo: #7C8CFF;
        --indigo-dim: rgba(124, 140, 255, 0.14);
        --copper: #E8A15C;
        --copper-dim: rgba(232, 161, 92, 0.14);
        --text-primary: #E9ECF7;
        --text-muted: #8891B5;
        --border-subtle: rgba(255, 255, 255, 0.07);
    }

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: 'Space Grotesk', sans-serif !important;
        letter-spacing: -0.01em;
    }
    code, .stCodeBlock, .stCaption, [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Ambient drifting gradient mesh — slow, quiet parallax-style motion */
    .stApp {
        background:
            radial-gradient(circle at 15% 20%, rgba(124,140,255,0.10) 0%, transparent 40%),
            radial-gradient(circle at 85% 75%, rgba(232,161,92,0.08) 0%, transparent 45%),
            radial-gradient(circle at 50% 100%, rgba(124,140,255,0.05) 0%, transparent 50%),
            var(--bg-deep);
        background-size: 200% 200%;
        animation: drift 32s ease-in-out infinite;
    }
    @keyframes drift {
        0%, 100% { background-position: 0% 0%, 100% 100%, 50% 100%; }
        50% { background-position: 8% 12%, 92% 88%, 55% 92%; }
    }

    /* Sidebar as a glass panel */
    [data-testid="stSidebar"] {
        background: rgba(16, 22, 42, 0.85);
        backdrop-filter: blur(12px);
        border-right: 1px solid var(--border-subtle);
    }

    /* Fade + rise entrance for the main block */
    .main .block-container { animation: rise 0.5s ease-out; }
    @keyframes rise {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, var(--indigo), #5B6BEE);
        color: #0A0E1A;
        font-weight: 600;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.2rem;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        box-shadow: 0 2px 12px rgba(124, 140, 255, 0.25);
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(124, 140, 255, 0.4);
    }
    .stButton > button:active { transform: translateY(0px); }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: var(--bg-surface);
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        padding: 0.9rem 1rem;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-3px);
        border-color: rgba(124, 140, 255, 0.35);
    }

    /* Expanders as quiet glass cards */
    [data-testid="stExpander"] {
        background: var(--bg-surface);
        border: 1px solid var(--border-subtle);
        border-radius: 12px;
        overflow: hidden;
    }

    /* Chat bubbles */
    [data-testid="stChatMessage"] {
        background: var(--bg-surface);
        border: 1px solid var(--border-subtle);
        border-radius: 14px;
        animation: rise 0.35s ease-out;
    }

    /* Progress bar shimmer */
    [data-testid="stProgressBar"] > div > div {
        background: linear-gradient(90deg, var(--indigo), var(--copper), var(--indigo));
        background-size: 200% 100%;
        animation: shimmer 1.6s linear infinite;
    }
    @keyframes shimmer {
        0% { background-position: 0% 0%; }
        100% { background-position: 200% 0%; }
    }

    /* Radio nav rendered as pill tabs */
    [data-testid="stSidebar"] [role="radiogroup"] { gap: 0.4rem; }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(124,140,255,0.25); border-radius: 8px; }

    .evidence-card {
        background: var(--bg-surface);
        border: 1px solid var(--border-subtle);
        border-left: 3px solid var(--card-accent, var(--indigo));
        border-radius: 10px;
        padding: 0.85rem 1rem;
        margin-bottom: 0.6rem;
        transition: transform 0.15s ease;
    }
    .evidence-card:hover { transform: translateX(3px); }

    .source-pill {
        display: inline-block;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        padding: 0.15rem 0.55rem;
        border-radius: 999px;
        font-weight: 500;
        letter-spacing: 0.02em;
    }
    .pill-docs { background: var(--indigo-dim); color: var(--indigo); }
    .pill-github { background: var(--copper-dim); color: var(--copper); }
    </style>
    """,
    unsafe_allow_html=True,
)


def _signature_header() -> None:
    """The one intentional visual flourish: two threads — documentation
    (indigo) and GitHub history (copper) — draw themselves in from
    opposite sides and converge at a single glowing point. That
    convergence is literally what this agent does to every question."""
    st.markdown(
        """
        <div style="position: relative; height: 92px; margin-bottom: 0.5rem;">
            <svg width="100%" height="92" viewBox="0 0 900 92" preserveAspectRatio="none"
                 style="position:absolute; top:0; left:0;">
                <defs>
                    <linearGradient id="gIndigo" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stop-color="#7C8CFF" stop-opacity="0"/>
                        <stop offset="100%" stop-color="#7C8CFF" stop-opacity="1"/>
                    </linearGradient>
                    <linearGradient id="gCopper" x1="1" y1="0" x2="0" y2="0">
                        <stop offset="0%" stop-color="#E8A15C" stop-opacity="0"/>
                        <stop offset="100%" stop-color="#E8A15C" stop-opacity="1"/>
                    </linearGradient>
                </defs>
                <path d="M0,26 C 220,26 320,46 450,46" stroke="url(#gIndigo)" stroke-width="2.5"
                      fill="none" stroke-dasharray="480" stroke-dashoffset="480">
                    <animate attributeName="stroke-dashoffset" from="480" to="0" dur="1.1s"
                             fill="freeze" calcMode="spline" keySplines="0.16,1,0.3,1"/>
                </path>
                <path d="M900,66 C 680,66 580,46 450,46" stroke="url(#gCopper)" stroke-width="2.5"
                      fill="none" stroke-dasharray="480" stroke-dashoffset="480">
                    <animate attributeName="stroke-dashoffset" from="480" to="0" dur="1.1s"
                             fill="freeze" calcMode="spline" keySplines="0.16,1,0.3,1"/>
                </path>
                <circle cx="450" cy="46" r="5" fill="#E9ECF7">
                    <animate attributeName="r" values="4;7;4" dur="2.4s" repeatCount="indefinite"/>
                    <animate attributeName="opacity" values="0;1" dur="0.4s" begin="1.0s" fill="freeze"/>
                </circle>
                <circle cx="450" cy="46" r="14" fill="none" stroke="#E9ECF7" stroke-width="1" opacity="0">
                    <animate attributeName="r" values="6;22" dur="2.4s" repeatCount="indefinite"/>
                    <animate attributeName="opacity" values="0.5;0" dur="2.4s" repeatCount="indefinite"/>
                </circle>
            </svg>
        </div>
        """,
        unsafe_allow_html=True,
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
st.sidebar.markdown(
    """
    <div style="font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:1.3rem;
                letter-spacing:-0.02em; margin-bottom:0.1rem;">
        <span style="color:#7C8CFF;">◆</span> Enterprise Knowledge Agent
    </div>
    <div style="color:#8891B5; font-size:0.82rem; margin-bottom:1rem;">
        Acme Corp · Nexus Integration Hub demo
    </div>
    """,
    unsafe_allow_html=True,
)
page = st.sidebar.radio("Navigate", ["Setup", "Chat"], index=0 if not st.session_state.kb_built else 1)

st.sidebar.markdown("---")

if not _check_api_key():
    st.sidebar.warning("Set GROQ_API_KEY in `.env` or Streamlit secrets.")


# ====================================================================
# SCREEN 1 — Setup / Knowledge Base Builder
# ====================================================================
if page == "Setup":
    _signature_header()
    st.markdown(
        "<h1 style='margin-top:0;'>Knowledge Base Builder</h1>", unsafe_allow_html=True
    )
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

        # Show feedback before the slow part: importing chromadb/transformers/
        # sentence-transformers can take 20-40s the first time in a process,
        # and used to happen silently before the progress bar even existed.
        progress = st.progress(0, text="Loading libraries (first run only)...")

        from src.ingestion.docs_ingestion import (
            index_doc_chunks,
            ingest_doc_bytes,
            ingest_docs_from_directory,
        )
        from src.ingestion.github_ingestion import fetch_github_history, index_github_items
        from src.ingestion.sample_data import load_sample_github_items
        from src.utils.vector_store import reset_collections

        progress.progress(5, text="Resetting vector store...")
        reset_collections()

        progress.progress(10, text="Loading embedding model (first run only, ~1-2 min)...")
        from src.utils.vector_store import get_embeddings

        get_embeddings()  # force load/download now so it's not hidden inside chunk indexing below

        progress.progress(25, text="Processing documents...")

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
                github_items = fetch_github_history(
                    repo_url,
                    on_progress=lambda msg: progress.progress(40, text=f"GitHub: {msg}"),
                )
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
    _signature_header()
    st.markdown("<h1 style='margin-top:0;'>Chat</h1>", unsafe_allow_html=True)

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
                    is_docs = ev.source_type == "docs"
                    accent = INDIGO if is_docs else COPPER
                    pill_class = "pill-docs" if is_docs else "pill-github"
                    pill_text = "DOCS" if is_docs else "GITHUB"
                    title_html = f'<a href="{url}" target="_blank" style="color:inherit;">{label}</a>' if url else label
                    snippet = ev.content[:280] + ("..." if len(ev.content) > 280 else "")
                    st.markdown(
                        f"""
                        <div class="evidence-card" style="--card-accent:{accent};">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.35rem;">
                                <span style="font-family:'Space Grotesk',sans-serif; font-weight:600;">{title_html}</span>
                                <span class="source-pill {pill_class}">{pill_text}</span>
                            </div>
                            <div style="color:#8891B5; font-size:0.78rem; font-family:'JetBrains Mono',monospace; margin-bottom:0.4rem;">
                                composite {ev.composite_score:.2f} · vector {ev.vector_score:.2f} · grounding {ev.grounding_score:.2f} ·
                                relevance {ev.relevance_score:.2f} · recency {ev.recency_score:.2f} · authority {ev.authority_score:.2f}
                            </div>
                            <div style="color:#C4CAE3; font-size:0.85rem; line-height:1.4;">{snippet}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No evidence ranked.")

        if trace.reconciliation_notes:
            with st.expander("Reconciliation Notes"):
                st.markdown(trace.reconciliation_notes)
