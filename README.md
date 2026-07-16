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
- Evidence ranking by recency + authority + relevance (not just cosine similarity)
- Reconciliation node that surfaces conflicts instead of silently merging
- Bounded self-correction loop with query rewriting

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
| Vector Store | ChromaDB (local persistent) | Zero infra, fast to iterate, works on Streamlit Cloud |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` (local) | Free, no extra API key; Groq has no embedding API |
| LLM | Groq `llama-3.3-70b-versatile` | Fast inference via Groq LPU; good structured JSON for grading |
| UI | Streamlit | Single Python file, no frontend build |
| Docs corpus | PDF (5 bundled files) | Realistic enterprise doc format; extracted via `pypdf` |
| GitHub Data | GitHub REST API + bundled sample | Live API for real repos; mock Acme Corp data for guaranteed conflict |

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
├── app.py                          # Streamlit UI (both screens)
├── src/
│   ├── state.py                    # LangGraph shared state (TypedDict)
│   ├── graph.py                    # StateGraph wiring + conditional edges
│   ├── models/schemas.py           # Pydantic models (Evidence, Grade, Citation)
│   ├── nodes/                      # One file per graph node
│   ├── ingestion/                  # Docs + GitHub + sample data loaders
│   └── utils/                      # LLM (Groq), embeddings, ChromaDB
├── docs/corpus/                    # Acme Corp PDF documentation (5 files)
├── data/sample_github_history.json # Mock GitHub data for acme-corp/nexus-integration-hub
├── scripts/generate_corpus_pdfs.py # Regenerate PDF corpus from source text
└── ARCHITECTURE.md                 # Interview prep write-up
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key ([console.groq.com](https://console.groq.com)) |
| `GITHUB_TOKEN` | No | Higher GitHub API rate limits for live repo mode |
| `GROQ_MODEL` | No | Default: `llama-3.3-70b-versatile` |
| `EMBEDDING_MODEL` | No | Default: `all-MiniLM-L6-v2` |

## License

MIT
