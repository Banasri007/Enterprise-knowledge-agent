# Enterprise Knowledge Agent

Multi-source RAG agent with self-healing retrieval, source reconciliation, and LangGraph orchestration. Built as an interview-grade demo of production RAG patterns.

**Demo scenario:** [Acme Corp](https://github.com/acme-corp/nexus-integration-hub) **Nexus Integration Hub** — enterprise middleware connecting SAP, Salesforce, and Workday. PDF docs describe OAuth 2.0 + SAML SSO auth; GitHub history shows a migration to API keys (intentional conflict for demo).

## Architecture

```
Question → Planner → [Docs Agent | GitHub Agent] → Evidence Ranker
         → Reconciler → (self-correct loop) → Final Answer + Citations
```

**Key differentiators from basic RAG:**
- Per-source grounding check before evidence flows downstream
- Hybrid retrieval (vector MMR + BM25) with multi-query expansion and cross-encoder reranking, not just cosine similarity
- Evidence ranking by recency + authority + relevance on top of that
- Reconciliation node that surfaces conflicts instead of silently merging
- Bounded self-correction loop with query rewriting

> **Note on the planner:** in practice, the planner routes to `both` sources for nearly every real question — the two-source demo scenario is designed so most questions genuinely need both. The "Planner Routing" panel was removed from the Chat UI's reasoning trace for this reason; the node itself is unchanged in `src/graph.py` and still runs, it just wasn't informative to show when the outcome barely varies.

## Quick Start (Local)

```bash
git clone <your-repo-url>
cd enterprise-knowledge-agent
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
cp .env.example .env           # add your GROQ_API_KEY
python scripts/generate_corpus_pdfs.py   # creates docs/corpus/*.pdf
streamlit run app.py
```

1. Go to **Setup** → enable "Use bundled Acme Corp sample data" → **Build Knowledge Base**
2. Switch to **Chat** and try the demo questions below

> `.streamlit/config.toml` sets `fileWatcherType = "none"`. Streamlit's dev-mode file watcher can otherwise trigger reruns that force the embedding model to reload from disk; if you edit source files during development, restart the server manually to pick up changes rather than relying on auto-reload.

## Demo Test Cases

| # | Question | Expected Route | What It Demonstrates |
|---|---|---|---|
| 1 | "How does API authentication work in this system?" | docs | Docs-only answer citing `authentication_guide.pdf` (OAuth 2.0 + SAML) |
| 2 | "When was API key authentication introduced?" | github | GitHub-only answer citing PR #142 / commits from `acme-corp/nexus-integration-hub` |
| 3 | "What authentication method does the system currently use?" | both | **Conflict**: PDF docs say OAuth/SAML, GitHub shows API key migration |

See [tests/test_cases.md](tests/test_cases.md) for full expected behavior.

## Tech Stack

| Component | Choice | Why |
|---|---|---|
| Orchestration | LangGraph `StateGraph` | Explicit routing, parallel fan-out, cyclical self-correction |
| Retrieval | Hybrid: Chroma vector (MMR) + BM25 via `EnsembleRetriever`, `MultiQueryRetriever` expansion, cross-encoder rerank (`ms-marco-MiniLM-L-6-v2`) | Catches both semantic matches and exact terms (identifiers, PR numbers) BM25-only or vector-only retrieval miss; reranking is more accurate than embedding similarity alone for final top-k |
| Vector Store | ChromaDB (local persistent), cached via `st.cache_resource` | Zero infra, fast to iterate, works on Streamlit Cloud; `st.cache_resource` (not `functools.lru_cache`) so the client/embedding model reliably survive Streamlit reruns |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` (local) | Free, no extra API key; Groq has no embedding API |
| LLM | Groq, two-tier: `llama-3.3-70b-versatile` for the final answer, `llama-3.1-8b-instant` for grading/reconciliation/query-rewrite steps | Grading nodes emit small structured JSON judgments that don't need 70B-scale reasoning — tiering cuts per-question latency significantly since a full pass makes 3-6 sequential LLM calls |
| UI | Streamlit, custom CSS theme | Single Python file, no frontend build |
| Docs corpus | PDF (5 bundled files) | Realistic enterprise doc format; extracted via `pypdf` |
| GitHub Data | GitHub REST API (repo files, commits+diffs, PRs+diffs+comments, issues+comments), parallelized fetch, or bundled sample | Live API for real repos, with concurrent per-item fetching (`ThreadPoolExecutor`) and an upfront rate-limit check; mock Acme Corp data for guaranteed conflict |

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. New app → select repo → main file: `app.py`
4. Add secrets: `GROQ_API_KEY` (and optionally `GITHUB_TOKEN`)
5. Deploy

## Deploy to Hugging Face Spaces

1. Create a new Space with SDK = **Streamlit**
2. Push repo contents (or connect GitHub)
3. Add `GROQ_API_KEY` in Space Settings → Variables and secrets
4. HF will auto-run `streamlit run app.py`

## Project Structure

```
├── app.py                          # Streamlit UI (both screens, custom dual-source CSS theme)
├── src/
│   ├── state.py                    # LangGraph shared state (TypedDict)
│   ├── graph.py                    # StateGraph wiring + conditional edges
│   ├── models/schemas.py           # Pydantic models (Evidence, Grade, Citation)
│   ├── nodes/                      # One file per graph node
│   ├── ingestion/                  # Docs + GitHub (parallelized) + sample data loaders
│   └── utils/                      # LLM (Groq, fast/slow tiers), retrieval (hybrid+rerank), ChromaDB
├── docs/corpus/                    # Acme Corp PDF documentation (5 files)
├── data/sample_github_history.json # Mock GitHub data for acme-corp/nexus-integration-hub
├── scripts/generate_corpus_pdfs.py # Regenerate PDF corpus from source text
└── ARCHITECTURE.md                 # Interview prep write-up
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key ([console.groq.com](https://console.groq.com)) |
| `GITHUB_TOKEN` | No | Higher GitHub API rate limits for live repo mode (5000/hr vs 60/hr unauthenticated — effectively required for live mode given ingestion's call volume) |
| `GROQ_MODEL` | No | Default: `llama-3.3-70b-versatile` (final answer generation) |
| `GROQ_FAST_MODEL` | No | Default: `llama-3.1-8b-instant` (grading, reconciliation, query-rewrite) |
| `EMBEDDING_MODEL` | No | Default: `all-MiniLM-L6-v2` |

## License

MIT
