"""Read-only GitHub lookups shared by the servers: a token from the environment, or the ``gh`` CLI's login."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Any

from dex_trove.mcp.common import Context, ToolError, http

REPO = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
AUTH_HINT = (
    "Set GH_TOKEN (or GITHUB_TOKEN) with read access to the repository, or log in with `gh auth login`."
)


def check_repo(repo: object) -> str:
    if not isinstance(repo, str) or not REPO.match(repo):
        raise ToolError(f"{repo!r} isn't a repository name like owner/name")
    return repo


def get(ctx: Context, path: str) -> Any:
    """GET ``path`` from the GitHub API (``/repos/...``)."""
    token = ctx.env.get("GH_TOKEN") or ctx.env.get("GITHUB_TOKEN")
    base = ctx.env.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    if token:
        resp = http(
            ctx,
            "GET",
            base + path,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "dex-trove-mcp",
            },
            service="GitHub",
            auth_hint=AUTH_HINT,
        )
        if resp.status == 404:
            raise ToolError(f"GitHub: {path} not found (or the token can't see it)")
        if resp.status >= 400:
            raise ToolError(f"GitHub answered {resp.status} for {path}")
        return resp.json()
    gh = shutil.which("gh")
    if not gh:
        raise ToolError("no GitHub credentials. " + AUTH_HINT)
    done = subprocess.run([gh, "api", path], capture_output=True, text=True, timeout=60, check=False)  # noqa: S603
    if done.returncode != 0:
        raise ToolError(f"gh api {path} failed: {done.stderr.strip()[:300] or 'no output'}. {AUTH_HINT}")
    try:
        return json.loads(done.stdout)
    except ValueError as exc:
        raise ToolError(f"gh api {path} didn't return JSON") from exc


def pr_status(ctx: Context, repo: str, number: int) -> dict[str, Any]:
    """Whether a pull request is open, its head commit, and whether every check on that commit passed."""
    check_repo(repo)
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise ToolError("pr must be a positive pull request number")
    pr = get(ctx, f"/repos/{repo}/pulls/{number}")
    sha = (pr.get("head") or {}).get("sha", "")
    runs = (
        get(ctx, f"/repos/{repo}/commits/{sha}/check-runs?per_page=100").get("check_runs", []) if sha else []
    )
    combined = get(ctx, f"/repos/{repo}/commits/{sha}/status") if sha else {}
    checks = [
        {"name": r.get("name", ""), "status": r.get("status", ""), "conclusion": r.get("conclusion")}
        for r in runs
    ]
    checks += [
        {
            "name": s.get("context", ""),
            "status": "completed" if s.get("state") != "pending" else "in_progress",
            "conclusion": {"success": "success", "pending": None}.get(s.get("state", ""), "failure"),
        }
        for s in combined.get("statuses", [])
    ]
    pending = [c["name"] for c in checks if c["status"] != "completed"]
    failed = [
        c["name"]
        for c in checks
        if c["status"] == "completed" and c["conclusion"] not in ("success", "neutral", "skipped")
    ]
    state = "failing" if failed else "pending" if pending else "passing" if checks else "none"
    return {
        "repo": repo,
        "number": number,
        "state": pr.get("state", ""),
        "draft": bool(pr.get("draft")),
        "head_sha": sha,
        "head_ref": (pr.get("head") or {}).get("ref", ""),
        "checks": state,
        "failed": sorted(failed),
        "pending": sorted(pending),
        "url": pr.get("html_url", ""),
    }
