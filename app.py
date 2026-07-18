"""Streamlit UI — Setup screen + Chat with reasoning panel."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

CORPUS_DIR = Path(__file__).parent / "docs" / "corpus"
SAMPLE_REPO_URL = "https://github.com/acme-corp/nexus-integration-hub"

# Monochrome visual language: docs vs GitHub is distinguished by weight/style
# (solid vs dashed border, pill treatment), not hue.
WHITE = "#F2F2F2"
GRAY = "#9A9A9A"

st.set_page_config(
    page_title="Enterprise Knowledge Agent",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
        --bg-deep: #050505;
        --bg-surface: #131313;
        --bg-surface-2: #1B1B1B;
        --white: #F2F2F2;
        --white-dim: rgba(242, 242, 242, 0.12);
        --gray: #9A9A9A;
        --gray-dim: rgba(154, 154, 154, 0.14);
        --text-primary: #F2F2F2;
        --text-muted: #8C8C8C;
        --border-subtle: rgba(255, 255, 255, 0.09);
    }

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: 'Space Grotesk', sans-serif !important;
        letter-spacing: -0.01em;
    }
    code, .stCodeBlock, .stCaption, [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Ambient background: a faint slow-drifting diagonal scanline texture,
       pure grayscale, quiet enough to sit behind text without competing */
    .stApp {
        background:
            repeating-linear-gradient(
                115deg,
                rgba(255,255,255,0.025) 0px,
                rgba(255,255,255,0.025) 1px,
                transparent 1px,
                transparent 68px
            ),
            radial-gradient(circle at 50% 0%, rgba(255,255,255,0.05) 0%, transparent 55%),
            var(--bg-deep);
        background-size: 140% 140%, 160% 160%, 100% 100%;
        animation: drift 40s ease-in-out infinite;
    }
    @keyframes drift {
        0%, 100% { background-position: 0% 0%, 30% 20%, 0 0; }
        50% { background-position: -6% 4%, 38% 30%, 0 0; }
    }

    /* Sidebar as a glass panel */
    [data-testid="stSidebar"] {
        background: rgba(19, 19, 19, 0.9);
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
        background: var(--white);
        color: #0A0A0A;
        font-weight: 600;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.2rem;
        transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
        box-shadow: 0 2px 14px rgba(255, 255, 255, 0.12);
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 22px rgba(255, 255, 255, 0.22);
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
        border-color: rgba(255, 255, 255, 0.3);
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
        background: linear-gradient(90deg, #4A4A4A, var(--white), #4A4A4A);
        background-size: 200% 100%;
        animation: shimmer 1.6s linear infinite;
    }
    @keyframes shimmer {
        0% { background-position: 0% 0%; }
        100% { background-position: 200% 0%; }
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 8px; }

    .evidence-card {
        background: var(--bg-surface);
        border: 1px solid var(--border-subtle);
        border-left: 3px solid var(--card-accent, var(--white));
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
    .pill-docs { background: var(--white-dim); color: var(--white); border: 1px solid rgba(255,255,255,0.25); }
    .pill-github { background: transparent; color: var(--gray); border: 1px dashed rgba(255,255,255,0.3); }

    /* Top nav tab-cards */
    div[data-testid="column"] .stButton > button {
        height: 64px;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1rem;
        border-radius: 14px;
    }
    div[data-testid="column"] .stButton > button[kind="secondary"] {
        background: var(--bg-surface);
        color: var(--text-muted);
        border: 1px solid var(--border-subtle);
        box-shadow: none;
    }
    div[data-testid="column"] .stButton > button[kind="secondary"]:hover {
        border-color: rgba(255, 255, 255, 0.4);
        color: var(--text-primary);
        transform: translateY(-2px);
    }
    div[data-testid="column"] .stButton > button[kind="primary"] {
        background: var(--white);
        box-shadow: 0 4px 24px rgba(255, 255, 255, 0.25);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _signature_header() -> None:
    """Signature visual: a radar sweep continuously scanning a field of
    pulsing rings that converge on a single core — evidence arriving from
    all directions and resolving to one point, rendered in monochrome."""
    html = (
        '<div style="position:relative;height:96px;margin-bottom:0.5rem;'
        'display:flex;align-items:center;justify-content:center;">'
        '<svg width="220" height="96" viewBox="0 0 220 96">'
        '<defs><radialGradient id="sweepGrad" cx="0%" cy="50%" r="100%">'
        '<stop offset="0%" stop-color="#F2F2F2" stop-opacity="0.55"/>'
        '<stop offset="100%" stop-color="#F2F2F2" stop-opacity="0"/>'
        '</radialGradient></defs>'
        '<circle cx="110" cy="48" r="18" fill="none" stroke="rgba(255,255,255,0.14)" stroke-width="1"/>'
        '<circle cx="110" cy="48" r="32" fill="none" stroke="rgba(255,255,255,0.10)" stroke-width="1"/>'
        '<circle cx="110" cy="48" r="45" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>'
        '<circle cx="110" cy="48" r="8" fill="none" stroke="#F2F2F2" stroke-width="1.4" opacity="0.7">'
        '<animate attributeName="r" values="8;45" dur="2.6s" repeatCount="indefinite"/>'
        '<animate attributeName="opacity" values="0.7;0" dur="2.6s" repeatCount="indefinite"/>'
        '</circle>'
        '<circle cx="110" cy="48" r="8" fill="none" stroke="#F2F2F2" stroke-width="1.4" opacity="0.7">'
        '<animate attributeName="r" values="8;45" dur="2.6s" begin="1.3s" repeatCount="indefinite"/>'
        '<animate attributeName="opacity" values="0.7;0" dur="2.6s" begin="1.3s" repeatCount="indefinite"/>'
        '</circle>'
        '<g transform-origin="110 48">'
        '<path d="M 110 48 L 110 3 A 45 45 0 0 1 141.8 16.2 Z" fill="url(#sweepGrad)"/>'
        '<animateTransform attributeName="transform" type="rotate" '
        'from="0 110 48" to="360 110 48" dur="3.2s" repeatCount="indefinite"/>'
        '</g>'
        '<circle cx="110" cy="48" r="4.5" fill="#F2F2F2">'
        '<animate attributeName="r" values="4;5.5;4" dur="1.8s" repeatCount="indefinite"/>'
        '</circle>'
        '</svg></div>'
    )
    st.markdown(
        html,
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


if "page" not in st.session_state:
    st.session_state.page = "Setup"

# --- Top nav: title + two tab-cards (replaces sidebar) ---
st.markdown(
    """
    <div style="display:flex; align-items:baseline; gap:0.6rem; margin-bottom:0.9rem;">
        <span style="font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:1.7rem;
                     letter-spacing:-0.02em; color:#F2F2F2;">
            <span style="color:#F2F2F2;">◆</span> Enterprise Knowledge Agent
        </span>
        <span style="color:#8C8C8C; font-size:0.88rem;">Acme Corp · Nexus Integration Hub demo</span>
    </div>
    """,
    unsafe_allow_html=True,
)

nav_col1, nav_col2 = st.columns(2, gap="medium")
with nav_col1:
    setup_active = st.session_state.page == "Setup"
    if st.button(
        ("◆ " if setup_active else "") + "Setup — Build Knowledge Base",
        key="nav_setup",
        use_container_width=True,
        type="primary" if setup_active else "secondary",
    ):
        st.session_state.page = "Setup"
        st.rerun()
with nav_col2:
    chat_active = st.session_state.page == "Chat"
    if st.button(
        ("◆ " if chat_active else "") + "Chat — Ask the Agent",
        key="nav_chat",
        use_container_width=True,
        type="primary" if chat_active else "secondary",
    ):
        st.session_state.page = "Chat"
        st.rerun()

page = st.session_state.page

if not _check_api_key():
    st.warning("Set GROQ_API_KEY in `.env` or Streamlit secrets.")

st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)


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
        st.session_state.page = "Chat"
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
                    accent = WHITE if is_docs else GRAY
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
