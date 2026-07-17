"""Pre-download and cache the embedding + reranker models locally.

Run this ONCE (locally, or as a build step in your deploy pipeline):

    python scripts/download_models.py

It saves both models under assets/models/, and the app's
get_embeddings()/get_reranker() will load from there directly instead of
hitting the Hugging Face Hub on every cold start. Commit assets/models/
to the repo (or bake it into your deploy image) so Streamlit Community
Cloud / HF Spaces never has to download anything at runtime.
"""

from __future__ import annotations

from pathlib import Path

from sentence_transformers import CrossEncoder, SentenceTransformer

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "models"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
RERANK_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

EMBEDDING_LOCAL_PATH = ASSETS_DIR / "embedding"
RERANK_LOCAL_PATH = ASSETS_DIR / "reranker"


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading embedding model '{EMBEDDING_MODEL_NAME}' ...")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    embedding_model.save(str(EMBEDDING_LOCAL_PATH))
    print(f"Saved to {EMBEDDING_LOCAL_PATH}")

    print(f"Downloading reranker model '{RERANK_MODEL_NAME}' ...")
    reranker_model = CrossEncoder(RERANK_MODEL_NAME)
    reranker_model.save(str(RERANK_LOCAL_PATH))
    print(f"Saved to {RERANK_LOCAL_PATH}")

    print("\nDone. Commit assets/models/ to the repo so deploys don't")
    print("need to hit the Hugging Face Hub at runtime.")


if __name__ == "__main__":
    main()
