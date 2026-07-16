"""Documentation corpus ingestion — PDF, markdown, and text."""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from src.models.schemas import DocChunk
from src.utils.vector_store import (
    DOCS_COLLECTION,
    add_to_collection,
    get_text_splitter,
)


def _extract_section(text: str) -> str:
    """Pull the nearest heading-like line for citation."""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    for line in lines[:5]:
        if len(line) < 80 and (line.isupper() or line.endswith(":") or line.startswith("#")):
            return line.lstrip("#").strip()
    headings = re.findall(r"^#{1,3}\s+(.+)$", text, re.MULTILINE)
    return headings[-1] if headings else "Introduction"


def _extract_pdf_text(raw: bytes) -> str:
    reader = PdfReader(BytesIO(raw))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def ingest_doc_file(filename: str, content: str) -> list[DocChunk]:
    """Chunk a single uploaded doc file."""
    splitter = get_text_splitter()
    chunks = splitter.split_text(content)
    doc_chunks: list[DocChunk] = []
    for idx, chunk in enumerate(chunks):
        doc_chunks.append(
            DocChunk(
                doc_name=filename,
                section=_extract_section(chunk),
                content=chunk,
                chunk_index=idx,
            )
        )
    return doc_chunks


def ingest_doc_bytes(filename: str, raw: bytes) -> list[DocChunk]:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        text = _extract_pdf_text(raw)
    else:
        text = raw.decode("utf-8", errors="replace")
    return ingest_doc_file(filename, text)


def ingest_docs_from_directory(docs_dir: Path) -> list[DocChunk]:
    """Load bundled docs from a directory (PDF preferred, then md/txt)."""
    all_chunks: list[DocChunk] = []
    patterns = ("*.pdf", "*.md", "*.txt")
    seen_stems: set[str] = set()

    for pattern in patterns:
        for path in sorted(docs_dir.glob(pattern)):
            stem = path.stem
            if stem in seen_stems:
                continue
            seen_stems.add(stem)
            if path.suffix.lower() == ".pdf":
                text = _extract_pdf_text(path.read_bytes())
            else:
                text = path.read_text(encoding="utf-8")
            all_chunks.extend(ingest_doc_file(path.name, text))
    return all_chunks


def index_doc_chunks(chunks: list[DocChunk]) -> int:
    """Embed and store doc chunks in Chroma."""
    if not chunks:
        return 0

    ids = [f"doc-{c.doc_name}-{c.chunk_index}" for c in chunks]
    documents = [c.content for c in chunks]
    metadatas = [
        {
            "source_type": "docs",
            "doc_name": c.doc_name,
            "section": c.section,
            "chunk_index": c.chunk_index,
        }
        for c in chunks
    ]
    add_to_collection(DOCS_COLLECTION, ids, documents, metadatas)
    return len(chunks)
