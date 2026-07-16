"""Pydantic models for evidence, grading, and citations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """A single retrieved piece of evidence from docs or GitHub."""

    source_type: Literal["docs", "github"]
    content: str
    metadata: dict = Field(default_factory=dict)
    vector_score: float = 0.0
    grounding_score: float = 0.0
    relevance_score: float = 0.0
    recency_score: float = 0.0
    authority_score: float = 0.0
    composite_score: float = 0.0

    @property
    def citation_label(self) -> str:
        if self.source_type == "docs":
            doc_name = self.metadata.get("doc_name", "unknown-doc")
            section = self.metadata.get("section", "")
            return f"{doc_name}" + (f" §{section}" if section else "")
        item_type = self.metadata.get("item_type", "commit")
        if item_type == "pr":
            return f"PR #{self.metadata.get('pr_number', '?')}"
        if item_type == "issue":
            return f"Issue #{self.metadata.get('issue_number', '?')}"
        if item_type == "comment":
            parent = self.metadata.get("pr_number") or self.metadata.get("issue_number")
            return f"Comment on #{parent}"
        if item_type == "file":
            return self.metadata.get("file_path", "repo file")
        return f"commit {self.metadata.get('sha', '?')[:7]}"

    @property
    def citation_url(self) -> str | None:
        if self.source_type == "github":
            return self.metadata.get("url")
        return None


class SourceGrade(BaseModel):
    """Grounding/relevance grade for a single source's retrieval batch."""

    source_type: Literal["docs", "github"]
    is_grounded: bool
    is_relevant: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    evidence_count: int = 0


class ConflictDetail(BaseModel):
    """Describes disagreement between docs and GitHub evidence."""

    topic: str
    docs_perspective: str
    github_perspective: str
    docs_citations: list[str] = Field(default_factory=list)
    github_citations: list[str] = Field(default_factory=list)
    resolution_note: str = ""


class Citation(BaseModel):
    """Citation attached to the final answer."""

    label: str
    source_type: Literal["docs", "github"]
    url: str | None = None
    excerpt: str = ""


class ReasoningTrace(BaseModel):
    """Full reasoning trace shown in the UI."""

    route: Literal["docs", "github", "both"] = "both"
    route_reason: str = ""
    docs_grade: SourceGrade | None = None
    github_grade: SourceGrade | None = None
    ranked_evidence: list[EvidenceItem] = Field(default_factory=list)
    conflict_detected: bool = False
    conflict_details: list[ConflictDetail] = Field(default_factory=list)
    reconciliation_notes: str = ""
    self_correction_triggered: bool = False
    self_correction_notes: str = ""
    original_query: str = ""
    rewritten_query: str = ""
    retry_count: int = 0


class DocChunk(BaseModel):
    """Structured doc chunk stored in the vector DB."""

    doc_name: str
    section: str
    content: str
    chunk_index: int


class GitHubItem(BaseModel):
    """Structured GitHub commit, PR, issue, comment, or repo file item."""

    item_type: Literal["commit", "pr", "issue", "comment", "file"]
    sha: str | None = None
    pr_number: int | None = None
    issue_number: int | None = None
    comment_id: int | None = None
    file_path: str | None = None
    title: str
    body: str
    author: str
    timestamp: datetime
    url: str
    files_changed: list[str] = Field(default_factory=list)
