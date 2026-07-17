"""GitHub history ingestion via GitHub API — commits (with diffs), PRs
(with diffs), issues, and comments."""

from __future__ import annotations

import base64
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable

import httpx

from src.models.schemas import GitHubItem
from src.utils.vector_store import GITHUB_COLLECTION, add_to_collection, get_text_splitter

GITHUB_API = "https://api.github.com"

# Bounds to keep ingestion time and API-rate-limit usage reasonable.
# Raise these if you have a GITHUB_TOKEN (5000 req/hr vs 60 unauthenticated).
MAX_COMMITS = 25
MAX_COMMITS_WITH_DIFF = 8
MAX_PRS = 10
MAX_ISSUES = 15
MAX_COMMENTS_PER_THREAD = 5
MAX_FILES_PER_ITEM = 5
PATCH_CHAR_LIMIT = 800
COMMENT_CHAR_LIMIT = 500
MAX_REPO_FILES = 25
MAX_FILE_BYTES = 40_000
REPO_FILE_EXTENSIONS = {
    ".md", ".txt", ".rst", ".html", ".htm",
    ".cs", ".cshtml", ".razor", ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".go", ".rb", ".php", ".json", ".yml", ".yaml", ".xml",
    ".sql", ".pli", ".pl1", ".cbl", ".cob",
}
SKIP_PATH_SEGMENTS = {"node_modules", ".git", "bin", "obj", "dist", "build", ".venv"}

# Per-item fetches (commit diffs, PR files, comments, repo file contents) are
# each a separate HTTP call. Running them one at a time was the main source
# of slowness (100+ sequential round trips). This bounds how many run at once.
MAX_WORKERS = 16


class GitHubRateLimitError(RuntimeError):
    """Raised when the GitHub API rate limit is exhausted mid-ingestion."""


def _parse_repo_url(repo_url: str) -> tuple[str, str]:
    """Extract owner/repo from a GitHub URL."""
    patterns = [
        r"github\.com/([^/]+)/([^/\.]+)",
        r"^([^/]+)/([^/]+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, repo_url.strip())
        if match:
            return match.group(1), match.group(2).removesuffix(".git")
    raise ValueError(f"Invalid GitHub repo URL: {repo_url}")


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _check_rate_limit(client: httpx.Client, min_needed: int = 40) -> None:
    """Fail fast with a clear error instead of silently losing data to 403s
    partway through ingestion. Unauthenticated requests get 60/hour; this
    pipeline can easily need 100-150+ calls for a repo with real history."""
    try:
        resp = client.get(f"{GITHUB_API}/rate_limit")
        resp.raise_for_status()
        core = resp.json().get("resources", {}).get("core", {})
        remaining = core.get("remaining", 0)
        limit = core.get("limit", 60)
    except httpx.HTTPError:
        return  # don't block ingestion just because the rate-limit check itself failed

    if remaining < min_needed:
        reset_ts = core.get("reset")
        reset_str = (
            datetime.fromtimestamp(reset_ts, tz=timezone.utc).strftime("%H:%M UTC")
            if reset_ts
            else "later"
        )
        hint = (
            "Add a GITHUB_TOKEN to raise your limit to 5000/hour."
            if limit <= 60
            else "Wait for the limit to reset."
        )
        raise GitHubRateLimitError(
            f"Only {remaining}/{limit} GitHub API requests remaining (resets ~{reset_str}). "
            f"This repo ingestion needs ~{min_needed}+ requests. {hint}"
        )


def _get_paginated(client: httpx.Client, url: str, max_pages: int = 5) -> list[dict]:
    items: list[dict] = []
    page_url: str | None = url
    pages = 0
    while page_url and pages < max_pages:
        resp = client.get(page_url)
        resp.raise_for_status()
        items.extend(resp.json())
        page_url = resp.links.get("next", {}).get("url")
        pages += 1
    return items


def _run_parallel(fetch_fn, work_items: list, max_workers: int = MAX_WORKERS) -> list:
    """Run fetch_fn(item) over work_items concurrently, preserving order.
    A single slow/failed item no longer stalls or silently drops the rest."""
    if not work_items:
        return []
    results: list = [None] * len(work_items)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx = {pool.submit(fetch_fn, item): i for i, item in enumerate(work_items)}
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except GitHubRateLimitError:
                raise
            except Exception:
                results[idx] = None
    return results


def _format_files(files: list[dict]) -> list[str]:
    """Turn a GitHub API `files` array into readable diff snippets."""
    out: list[str] = []
    for f in files[:MAX_FILES_PER_ITEM]:
        filename = f.get("filename", "unknown")
        status = f.get("status", "modified")
        patch = (f.get("patch") or "")[:PATCH_CHAR_LIMIT]
        entry = f"{filename} ({status}, +{f.get('additions', 0)}/-{f.get('deletions', 0)})"
        if patch:
            entry += f"\n{patch}"
        out.append(entry)
    return out


def _raise_if_rate_limited(resp: httpx.Response) -> None:
    if resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0":
        raise GitHubRateLimitError(
            "GitHub API rate limit hit mid-ingestion. Add a GITHUB_TOKEN and retry."
        )


def _fetch_commit_files(client: httpx.Client, owner: str, repo: str, sha: str) -> list[str]:
    """Fetch the file diff for a single commit (one extra API call each)."""
    try:
        resp = client.get(f"{GITHUB_API}/repos/{owner}/{repo}/commits/{sha}")
        _raise_if_rate_limited(resp)
        resp.raise_for_status()
        return _format_files(resp.json().get("files", []))
    except GitHubRateLimitError:
        raise
    except httpx.HTTPError:
        return []


def _fetch_pr_files(client: httpx.Client, owner: str, repo: str, number: int) -> list[str]:
    try:
        resp = client.get(f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{number}/files")
        _raise_if_rate_limited(resp)
        resp.raise_for_status()
        return _format_files(resp.json())
    except GitHubRateLimitError:
        raise
    except httpx.HTTPError:
        return []


def _fetch_comments(client: httpx.Client, owner: str, repo: str, number: int) -> list[dict]:
    """Fetch general discussion comments on an issue or PR (PRs are issues in the GitHub API)."""
    try:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{number}/comments?per_page={MAX_COMMENTS_PER_THREAD}"
        resp = client.get(url)
        _raise_if_rate_limited(resp)
        resp.raise_for_status()
        return resp.json()[:MAX_COMMENTS_PER_THREAD]
    except GitHubRateLimitError:
        raise
    except httpx.HTTPError:
        return []


def fetch_commits(
    client: httpx.Client, owner: str, repo: str, limit: int = MAX_COMMITS
) -> list[GitHubItem]:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/commits?per_page=30"
    raw = _get_paginated(client, url, max_pages=3)[:limit]

    diff_targets = raw[:MAX_COMMITS_WITH_DIFF]
    diffs = _run_parallel(
        lambda c: _fetch_commit_files(client, owner, repo, c.get("sha", "")), diff_targets
    )
    files_by_sha = {c.get("sha", ""): d for c, d in zip(diff_targets, diffs)}

    items: list[GitHubItem] = []
    for c in raw:
        commit = c.get("commit", {})
        msg = commit.get("message", "")
        ts = commit.get("author", {}).get("date") or commit.get("committer", {}).get("date")
        sha = c.get("sha", "")
        items.append(
            GitHubItem(
                item_type="commit",
                sha=sha,
                title=msg.split("\n")[0][:200],
                body=msg,
                author=(c.get("author") or {}).get("login", "unknown"),
                timestamp=datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if ts
                else datetime.now(timezone.utc),
                url=c.get("html_url", ""),
                files_changed=files_by_sha.get(sha) or [],
            )
        )
    return items


def fetch_pull_requests(
    client: httpx.Client, owner: str, repo: str, limit: int = MAX_PRS
) -> tuple[list[GitHubItem], list[GitHubItem]]:
    """Returns (prs, pr_comments)."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls?state=all&per_page=20"
    raw = _get_paginated(client, url, max_pages=2)[:limit]

    numbers = [pr.get("number") for pr in raw]
    files_lists = _run_parallel(lambda n: _fetch_pr_files(client, owner, repo, n), numbers)
    comments_lists = _run_parallel(lambda n: _fetch_comments(client, owner, repo, n), numbers)

    prs: list[GitHubItem] = []
    comments: list[GitHubItem] = []
    for pr, files, raw_comments in zip(raw, files_lists, comments_lists):
        number = pr.get("number")
        merged = pr.get("merged_at")
        ts = merged or pr.get("created_at")
        prs.append(
            GitHubItem(
                item_type="pr",
                pr_number=number,
                title=pr.get("title", ""),
                body=pr.get("body") or "",
                author=(pr.get("user") or {}).get("login", "unknown"),
                timestamp=datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if ts
                else datetime.now(timezone.utc),
                url=pr.get("html_url", ""),
                files_changed=files or [],
            )
        )
        comments.extend(_comments_to_items(raw_comments or [], pr_number=number))
    return prs, comments


def fetch_issues(
    client: httpx.Client, owner: str, repo: str, limit: int = MAX_ISSUES
) -> tuple[list[GitHubItem], list[GitHubItem]]:
    """Returns (issues, issue_comments). Filters out PRs, which the
    `/issues` endpoint also returns."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues?state=all&per_page=30"
    raw = _get_paginated(client, url, max_pages=3)
    raw = [i for i in raw if "pull_request" not in i][:limit]

    numbers = [issue.get("number") for issue in raw]
    comments_lists = _run_parallel(lambda n: _fetch_comments(client, owner, repo, n), numbers)

    issues: list[GitHubItem] = []
    comments: list[GitHubItem] = []
    for issue, raw_comments in zip(raw, comments_lists):
        number = issue.get("number")
        ts = issue.get("created_at")
        issues.append(
            GitHubItem(
                item_type="issue",
                issue_number=number,
                title=issue.get("title", ""),
                body=issue.get("body") or "",
                author=(issue.get("user") or {}).get("login", "unknown"),
                timestamp=datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if ts
                else datetime.now(timezone.utc),
                url=issue.get("html_url", ""),
            )
        )
        comments.extend(_comments_to_items(raw_comments or [], issue_number=number))
    return issues, comments


def _comments_to_items(
    raw_comments: list[dict],
    pr_number: int | None = None,
    issue_number: int | None = None,
) -> list[GitHubItem]:
    items: list[GitHubItem] = []
    for c in raw_comments:
        ts = c.get("created_at")
        body = (c.get("body") or "")[:COMMENT_CHAR_LIMIT]
        parent = f"PR #{pr_number}" if pr_number else f"Issue #{issue_number}"
        items.append(
            GitHubItem(
                item_type="comment",
                pr_number=pr_number,
                issue_number=issue_number,
                comment_id=c.get("id"),
                title=f"Comment on {parent}",
                body=body,
                author=(c.get("user") or {}).get("login", "unknown"),
                timestamp=datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if ts
                else datetime.now(timezone.utc),
                url=c.get("html_url", ""),
            )
        )
    return items


def _get_default_branch(client: httpx.Client, owner: str, repo: str) -> str:
    resp = client.get(f"{GITHUB_API}/repos/{owner}/{repo}")
    resp.raise_for_status()
    return resp.json().get("default_branch", "main")


def _fetch_file_content(
    client: httpx.Client, owner: str, repo: str, branch: str, path: str
) -> GitHubItem | None:
    try:
        resp = client.get(f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}?ref={branch}")
        _raise_if_rate_limited(resp)
        resp.raise_for_status()
        data = resp.json()
        if data.get("encoding") != "base64":
            return None
        content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    except GitHubRateLimitError:
        raise
    except (httpx.HTTPError, KeyError, ValueError):
        return None

    return GitHubItem(
        item_type="file",
        file_path=path,
        title=path,
        body=content,
        author=owner,
        timestamp=datetime.now(timezone.utc),
        url=data.get("html_url", f"https://github.com/{owner}/{repo}/blob/{branch}/{path}"),
    )


def fetch_repo_files(client: httpx.Client, owner: str, repo: str) -> list[GitHubItem]:
    """Fetch actual repo file contents (README, source, docs, etc.) via the
    Git Trees + Contents API. This is what lets the KB answer questions
    about things that only exist as files in the repo (e.g. a README
    describing screens/architecture), not just commit/PR/issue history."""
    branch = _get_default_branch(client, owner, repo)
    try:
        resp = client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        )
        resp.raise_for_status()
        tree = resp.json().get("tree", [])
    except httpx.HTTPError:
        return []

    candidates = []
    for entry in tree:
        if entry.get("type") != "blob":
            continue
        path = entry.get("path", "")
        if any(seg in SKIP_PATH_SEGMENTS for seg in path.split("/")):
            continue
        ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if ext not in REPO_FILE_EXTENSIONS:
            continue
        if entry.get("size", 0) > MAX_FILE_BYTES:
            continue
        candidates.append(entry)

    # Prioritize README and top-level docs so they're never crowded out
    # by MAX_REPO_FILES on larger repos.
    candidates.sort(key=lambda e: (0 if "readme" in e["path"].lower() else 1, e["path"].count("/")))
    candidates = candidates[:MAX_REPO_FILES]

    fetched = _run_parallel(
        lambda entry: _fetch_file_content(client, owner, repo, branch, entry["path"]), candidates
    )
    return [item for item in fetched if item is not None]


def fetch_github_history(
    repo_url: str, on_progress: "Callable[[str], None] | None" = None
) -> list[GitHubItem]:
    """Fetch repo files (README/source/docs), commits (+diffs),
    PRs (+diffs +comments), and issues (+comments).

    on_progress, if given, is called with a short status string before
    each stage — this is what lets the UI show which stage is actually
    slow instead of a single opaque spinner for the whole thing.
    """
    owner, repo = _parse_repo_url(repo_url)

    def _report(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    with httpx.Client(timeout=30.0, headers=_headers()) as client:
        _check_rate_limit(client)

        _report("Fetching repo files...")
        t0 = time.monotonic()
        files = fetch_repo_files(client, owner, repo)
        _report(f"Repo files: {len(files)} in {time.monotonic() - t0:.1f}s")

        _report("Fetching commits...")
        t0 = time.monotonic()
        commits = fetch_commits(client, owner, repo)
        _report(f"Commits: {len(commits)} in {time.monotonic() - t0:.1f}s")

        _report("Fetching pull requests...")
        t0 = time.monotonic()
        prs, pr_comments = fetch_pull_requests(client, owner, repo)
        _report(f"PRs: {len(prs)} (+{len(pr_comments)} comments) in {time.monotonic() - t0:.1f}s")

        _report("Fetching issues...")
        t0 = time.monotonic()
        issues, issue_comments = fetch_issues(client, owner, repo)
        _report(
            f"Issues: {len(issues)} (+{len(issue_comments)} comments) in {time.monotonic() - t0:.1f}s"
        )

    return files + commits + prs + pr_comments + issues + issue_comments


def _item_to_document(item: GitHubItem) -> str:
    if item.item_type == "file":
        return f"File: {item.file_path}\n\n{item.body}"

    prefix = {
        "pr": "Pull Request",
        "commit": "Commit",
        "issue": "Issue",
        "comment": "Comment",
    }[item.item_type]
    if item.item_type == "pr":
        identifier = f"#{item.pr_number}"
    elif item.item_type == "issue":
        identifier = f"#{item.issue_number}"
    elif item.item_type == "comment":
        identifier = f"#{item.comment_id}"
    else:
        identifier = (item.sha or "")[:12]

    parts = [
        f"{prefix} {identifier}",
        f"Title: {item.title}",
        f"Author: {item.author}",
        f"Date: {item.timestamp.isoformat()}",
        f"Description:\n{item.body}",
    ]
    if item.files_changed:
        parts.append("Files changed:\n" + "\n\n".join(item.files_changed))
    return "\n".join(parts)


def index_github_items(items: list[GitHubItem]) -> int:
    if not items:
        return 0

    splitter = get_text_splitter()
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for item in items:
        if item.item_type == "file":
            chunks = splitter.split_text(item.body) or [item.body]
            for idx, chunk in enumerate(chunks):
                ids.append(f"file-{item.file_path}-{idx}")
                documents.append(f"File: {item.file_path} (part {idx + 1}/{len(chunks)})\n\n{chunk}")
                metadatas.append(
                    {
                        "source_type": "github",
                        "item_type": "file",
                        "file_path": item.file_path or "",
                        "chunk_index": idx,
                        "title": item.title,
                        "author": item.author,
                        "timestamp": item.timestamp.isoformat(),
                        "url": item.url,
                    }
                )
            continue

        if item.item_type == "pr":
            doc_id = f"pr-{item.pr_number}"
        elif item.item_type == "issue":
            doc_id = f"issue-{item.issue_number}"
        elif item.item_type == "comment":
            doc_id = f"comment-{item.comment_id}"
        else:
            doc_id = f"commit-{item.sha}"
        ids.append(doc_id)
        documents.append(_item_to_document(item))
        metadatas.append(
            {
                "source_type": "github",
                "item_type": item.item_type,
                "sha": item.sha or "",
                "pr_number": item.pr_number or 0,
                "issue_number": item.issue_number or 0,
                "comment_id": item.comment_id or 0,
                "title": item.title,
                "author": item.author,
                "timestamp": item.timestamp.isoformat(),
                "url": item.url,
                "has_files": bool(item.files_changed),
            }
        )

    add_to_collection(GITHUB_COLLECTION, ids, documents, metadatas)
    return len(items)
