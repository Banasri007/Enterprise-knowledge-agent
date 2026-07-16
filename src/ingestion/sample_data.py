"""Load sample GitHub history for demo conflict scenarios."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.models.schemas import GitHubItem

SAMPLE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "sample_github_history.json"


def load_sample_github_items() -> list[GitHubItem]:
    """Load bundled sample commits/PRs that conflict with docs corpus."""
    raw = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    items: list[GitHubItem] = []
    for entry in raw:
        items.append(
            GitHubItem(
                item_type=entry["item_type"],
                sha=entry.get("sha"),
                pr_number=entry.get("pr_number"),
                title=entry["title"],
                body=entry["body"],
                author=entry["author"],
                timestamp=datetime.fromisoformat(entry["timestamp"]),
                url=entry["url"],
            )
        )
    return items
