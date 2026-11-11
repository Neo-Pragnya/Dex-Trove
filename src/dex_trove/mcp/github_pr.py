"""Pull requests with evidence: a local preview first, then push and create only on approval, then attach evidence.

* ``github_pr_preview`` reads the branch, the commits ahead of the base and a PR body file (``dev review
  --pr-body`` writes one), hashes the evidence files, and writes a static preview (HTML with no forms, scripts or
  network access, plus Markdown). The page itself can't create anything: only the approved tool can.
* ``github_pr_create`` pushes the previewed commit and opens the pull request with ``gh``. It needs
  ``--allow-actions`` and the preview's approval digest; if a pull request for the branch exists already, it's
  returned instead of a second one. Each step's outcome is reported, so a push that worked and a create that
  failed is said as such.
* ``github_pr_attach`` re-hashes the evidence, refuses any file that changed since the preview, and posts a comment
  listing every file with its sha256 (and uploads the files to a release when asked).
"""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
from typing import Any

from dex_trove.mcp.common import (
    Context,
    ToolError,
    approval_for,
    artifact,
    redact,
    require_approval,
    result,
    sha256_file,
    write_json,
    write_text,
)
from dex_trove.mcp.server import Tool

NAME = "github"
TITLE = "GitHub: approved pull requests with evidence"
CAPABILITIES = ("CAP-pr-release-03", "CAP-pr-release-04")
INSTRUCTIONS = (
    "Opens pull requests only after a person approves a local preview. Order: github_pr_preview (writes a static "
    "preview, returns an approval digest; show the preview to the user), github_pr_create with that digest after an "
    "explicit yes (needs the server started with --allow-actions), then github_pr_attach to post evidence hashes."
)
BRANCH = re.compile(r"^(?!-)(?!.*\.\.)[A-Za-z0-9._/-]{1,200}$")
MAX_ARTIFACTS = 50
CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"


def _tool(ctx: Context, name: str) -> str:
    found = shutil.which(name, path=ctx.env.get("PATH"))
    if not found:
        raise ToolError(
            f"{name} isn't installed or isn't on PATH"
            + (" (install GitHub CLI and run gh auth login)" if name == "gh" else "")
        )
    return found


def _run(
    ctx: Context, argv: list[str], *, check: bool = True, timeout: int = 120
) -> subprocess.CompletedProcess[str]:
    exe = _tool(ctx, argv[0])
    done = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [exe, *argv[1:]],
        cwd=ctx.root,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=dict(ctx.env),
    )
    if check and done.returncode != 0:
        raise ToolError(
            f"{' '.join(argv[:3])} failed ({done.returncode}): {redact(done.stderr.strip())[:400] or 'no output'}"
        )
    return done


def _git(ctx: Context, *args: str) -> str:
    return _run(ctx, ["git", *args]).stdout.strip()


def _branch(value: object, what: str) -> str:
    if not isinstance(value, str) or not BRANCH.match(value):
        raise ToolError(f"{what} {value!r} isn't a valid branch name")
    return value


def _artifacts(ctx: Context, paths: list[str]) -> list[dict[str, Any]]:
    if len(paths) > MAX_ARTIFACTS:
        raise ToolError(f"at most {MAX_ARTIFACTS} evidence files")
    out = []
    for value in paths:
        path = ctx.path(value)
        if not path.is_file():
            raise ToolError(f"{value}: not a file")
        out.append(
            {
                "path": path.relative_to(ctx.root).as_posix(),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return sorted(out, key=lambda a: a["path"])


def _plan(ctx: Context, args: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    if _git(ctx, "rev-parse", "--is-inside-work-tree") != "true":
        raise ToolError(f"{ctx.root} isn't a git repository")
    branch = _branch(args.get("branch") or _git(ctx, "rev-parse", "--abbrev-ref", "HEAD"), "branch")
    base = _branch(args.get("base") or "main", "base")
    remote = args.get("remote") or "origin"
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", remote):
        raise ToolError(f"remote {remote!r} isn't a valid remote name")
    body_path = ctx.path(args["body"])
    body = body_path.read_text(encoding="utf-8")
    title = (
        args.get("title") or next((ln.lstrip("# ").strip() for ln in body.splitlines() if ln.strip()), "")
    ).strip()
    if not title:
        raise ToolError("no title: pass title, or start the body file with a heading")
    head = _git(ctx, "rev-parse", "HEAD")
    problems = []
    if branch == base:
        problems.append(f"the branch is the base ({base}); create a feature branch first")
    if branch == "HEAD":
        problems.append("HEAD is detached; check out a branch")
    dirty = _git(ctx, "status", "--porcelain", "--untracked-files=no")
    if dirty:
        problems.append(
            "there are uncommitted changes to tracked files; commit or stash them so the PR matches the evidence"
        )
    merge_base = _run(ctx, ["git", "merge-base", base, head], check=False)
    commits = []
    if merge_base.returncode == 0:
        log = _git(ctx, "log", "--format=%H %s", f"{merge_base.stdout.strip()}..{head}")
        commits = [{"sha": ln[:40], "subject": ln[41:]} for ln in log.splitlines() if ln]
        if not commits:
            problems.append(f"no commits ahead of {base}")
    else:
        problems.append(f"base branch {base} isn't known locally (git fetch {remote} {base})")
    plan = {
        "action": "github.pr",
        "remote": remote,
        "remote_url": redact(_run(ctx, ["git", "remote", "get-url", remote], check=False).stdout.strip()),
        "branch": branch,
        "base": base,
        "head_sha": head,
        "title": title[:250],
        "draft": bool(args.get("draft", True)),
        "body_sha256": sha256_file(body_path),
        "commits": commits,
        "evidence": _artifacts(ctx, args.get("evidence") or []),
    }
    return plan, problems


def _evidence_table(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return ""
    rows = "\n".join(f"| `{e['path']}` | `{e['sha256']}` | {e['bytes']} |" for e in evidence)
    return f"\n\n## Evidence\n\n| File | sha256 | Bytes |\n| --- | --- | --- |\n{rows}\n"


def _preview_html(plan: dict[str, Any], body: str, problems: list[str]) -> str:
    esc = html.escape
    commits = "".join(
        f"<li><code>{esc(c['sha'][:12])}</code> {esc(c['subject'])}</li>" for c in plan["commits"]
    )
    evidence = "".join(
        f"<tr><td><code>{esc(e['path'])}</code></td><td><code>{esc(e['sha256'])}</code></td><td>{e['bytes']}</td></tr>"
        for e in plan["evidence"]
    )
    blocked = "".join(f"<li>{esc(p)}</li>" for p in problems)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP}"><title>PR preview: {esc(plan["title"])}</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem;color:#1d2330;background:#fff}}
code,pre{{font-family:ui-monospace,monospace;font-size:13px}}pre{{white-space:pre-wrap;background:#f5f6f8;padding:1rem;border-radius:6px}}
table{{border-collapse:collapse}}td{{border:1px solid #d6d9df;padding:.3rem .6rem}}.warn{{background:#fff4e5;padding:.5rem 1rem;border-radius:6px}}</style>
</head><body>
<p><strong>Preview only.</strong> This page can't create or change anything. The pull request is opened by the approved
<code>github_pr_create</code> call with approval <code>{esc(approval_for(plan))}</code>.</p>
{f'<div class="warn"><strong>Blocked:</strong><ul>{blocked}</ul></div>' if blocked else ""}
<h1>{esc(plan["title"])}</h1>
<p><code>{esc(plan["branch"])}</code> into <code>{esc(plan["base"])}</code> at <code>{esc(plan["head_sha"][:12])}</code>
on {esc(plan["remote_url"] or plan["remote"])}{" as a draft" if plan["draft"] else ""}</p>
<h2>Commits</h2><ul>{commits}</ul>
<h2>Body</h2><pre>{esc(body)}</pre>
<h2>Evidence</h2><table><tr><td>File</td><td>sha256</td><td>Bytes</td></tr>{evidence}</table>
</body></html>
"""


def preview(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    plan, problems = _plan(ctx, args)
    body = ctx.path(args["body"]).read_text(encoding="utf-8") + _evidence_table(plan["evidence"])
    page = write_text(ctx.evidence / "pr-preview.html", _preview_html(plan, body, problems))
    markdown = write_text(ctx.evidence / "pr-preview.md", f"# {plan['title']}\n\n{body}")
    plan_file = write_json(ctx.evidence / "pr-plan.json", plan)
    return result(
        ctx,
        "blocked" if problems else "needs-approval",
        plan=plan,
        blocked_by=problems,
        approval=None if problems else approval_for(plan),
        actions_enabled=ctx.allow_actions,
        artifacts=[
            artifact(ctx, page, "text/html"),
            artifact(ctx, markdown, "text/markdown"),
            artifact(ctx, plan_file, "application/json", schema="dex-trove/pr-plan@1"),
        ],
        inputs=args,
    )


def _existing(ctx: Context, plan: dict[str, Any]) -> dict[str, Any] | None:
    done = _run(
        ctx, ["gh", "pr", "view", plan["branch"], "--json", "number,url,state,headRefOid"], check=False
    )
    if done.returncode != 0:
        return None
    try:
        data = json.loads(done.stdout)
    except ValueError:
        return None
    return data if isinstance(data, dict) and data.get("state") == "OPEN" else None


def create(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    plan, problems = _plan(ctx, args)
    if problems:
        raise ToolError("not creating: " + "; ".join(problems))
    require_approval(ctx, plan, args.get("approval"), action="github.pr")
    steps: list[dict[str, Any]] = []
    existing = _existing(ctx, plan)
    if existing:
        ctx.audit("duplicate", action="github.pr", url=existing.get("url"))
        return result(ctx, "already-open", pr=existing, steps=steps, inputs=args)
    push = _run(
        ctx, ["git", "push", plan["remote"], f"{plan['head_sha']}:refs/heads/{plan['branch']}"], check=False
    )
    steps.append({"step": "push", "ok": push.returncode == 0, "detail": redact(push.stderr.strip())[-400:]})
    if push.returncode != 0:
        ctx.audit("failed", action="github.pr", step="push")
        return result(
            ctx,
            "failed",
            steps=steps,
            warnings=["the push failed, so no pull request was created"],
            inputs=args,
        )
    body = ctx.path(args["body"]).read_text(encoding="utf-8") + _evidence_table(plan["evidence"])
    body_file = write_text(ctx.state / "pr-body.md", body)
    argv = [
        "gh",
        "pr",
        "create",
        "--base",
        plan["base"],
        "--head",
        plan["branch"],
        "--title",
        plan["title"],
        "--body-file",
        str(body_file),
    ]
    if plan["draft"]:
        argv.append("--draft")
    made = _run(ctx, argv, check=False)
    url = next((w for w in made.stdout.split() if w.startswith("https://")), "")
    steps.append(
        {
            "step": "create",
            "ok": made.returncode == 0,
            "detail": redact((made.stderr or made.stdout).strip())[-400:],
        }
    )
    if made.returncode != 0:
        ctx.audit("failed", action="github.pr", step="create")
        return result(
            ctx,
            "failed",
            steps=steps,
            warnings=[
                f"pushed {plan['branch']}, but creating the pull request failed: "
                "run github_pr_create again after fixing it (the push won't repeat)"
            ],
            inputs=args,
        )
    record = write_json(
        ctx.evidence / "pr-created.json", {"schema": "dex-trove/pr-created@1", "url": url, "plan": plan}
    )
    ctx.audit("created", action="github.pr", url=url)
    return result(
        ctx,
        "created",
        url=url,
        steps=steps,
        artifacts=[artifact(ctx, record, "application/json")],
        inputs=args,
    )


def _attach_plan(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    number = args["pr"]
    if number < 1:
        raise ToolError("pr must be a positive number")
    tag = args.get("release_tag")
    if tag is not None and not re.fullmatch(r"[A-Za-z0-9._/-]{1,100}", tag):
        raise ToolError(f"release_tag {tag!r} isn't a valid tag")
    expected = args.get("expected") or {}
    evidence = _artifacts(ctx, args["evidence"])
    changed = [e["path"] for e in evidence if e["path"] in expected and expected[e["path"]] != e["sha256"]]
    if changed:
        raise ToolError(
            f"evidence changed since it was recorded: {', '.join(changed)}. Nothing was attached; rerun the checks "
            "that produce it, then preview again."
        )
    return {"action": "github.attach", "pr": number, "release_tag": tag, "evidence": evidence}


def attach_preview(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    plan = _attach_plan(ctx, args)
    comment = "## Evidence" + _evidence_table(plan["evidence"]).split("## Evidence", 1)[1]
    return result(
        ctx,
        "needs-approval",
        plan=plan,
        comment=comment,
        approval=approval_for(plan),
        actions_enabled=ctx.allow_actions,
        inputs=args,
    )


def attach(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    plan = _attach_plan(ctx, args)
    require_approval(ctx, plan, args.get("approval"), action="github.attach")
    steps = []
    if plan["release_tag"]:
        up = _run(
            ctx,
            ["gh", "release", "upload", plan["release_tag"], *[e["path"] for e in plan["evidence"]]],
            check=False,
        )
        steps.append(
            {"step": "release-upload", "ok": up.returncode == 0, "detail": redact(up.stderr.strip())[-400:]}
        )
        if up.returncode != 0:
            return result(
                ctx,
                "failed",
                steps=steps,
                warnings=["the upload failed (an asset with that name may exist already)"],
                inputs=args,
            )
    comment = "## Evidence" + _evidence_table(plan["evidence"]).split("## Evidence", 1)[1]
    if plan["release_tag"]:
        comment += f"\nUploaded to release `{plan['release_tag']}`.\n"
    comment_file = write_text(ctx.state / f"pr-{plan['pr']}-evidence.md", comment)
    posted = _run(
        ctx, ["gh", "pr", "comment", str(plan["pr"]), "--body-file", str(comment_file)], check=False
    )
    steps.append(
        {
            "step": "comment",
            "ok": posted.returncode == 0,
            "detail": redact((posted.stderr or posted.stdout).strip())[-400:],
        }
    )
    ctx.audit("attached" if posted.returncode == 0 else "failed", action="github.attach", pr=plan["pr"])
    return result(ctx, "attached" if posted.returncode == 0 else "failed", steps=steps, inputs=args)


_BODY = {
    "type": "string",
    "description": "PR body Markdown file in the project (e.g. from dev review --pr-body)",
}
_EVIDENCE = {"type": "array", "items": {"type": "string"}, "description": "Evidence files to hash and list"}
_COMMON: dict[str, dict[str, Any]] = {
    "body": _BODY,
    "title": {"type": "string"},
    "branch": {"type": "string", "description": "Default: the current branch"},
    "base": {"type": "string", "description": "Default: main"},
    "remote": {"type": "string", "description": "Default: origin"},
    "draft": {"type": "boolean", "description": "Default: true"},
    "evidence": _EVIDENCE,
}
_ATTACH: dict[str, dict[str, Any]] = {
    "pr": {"type": "integer"},
    "evidence": _EVIDENCE,
    "expected": {"type": "object", "description": "path: sha256 recorded earlier; a changed file is refused"},
    "release_tag": {"type": "string", "description": "Also upload the files to this release"},
}

TOOLS = [
    Tool(
        "github_pr_preview",
        "Branch, commits, title, body and evidence hashes as a static local preview, with an approval digest. "
        "Pushes and creates nothing.",
        _COMMON,
        preview,
        required=("body",),
        writes=True,
    ),
    Tool(
        "github_pr_create",
        "Pushes the previewed commit and opens the pull request. Needs --allow-actions and the approval digest "
        "the user accepted; returns the existing PR instead of a duplicate.",
        {**_COMMON, "approval": {"type": "string"}},
        create,
        required=("body", "approval"),
        action=True,
    ),
    Tool(
        "github_pr_attach_preview",
        "Re-hashes evidence for a PR and shows the comment that would be posted. Posts nothing.",
        _ATTACH,
        attach_preview,
        required=("pr", "evidence"),
    ),
    Tool(
        "github_pr_attach",
        "Posts the evidence comment (and uploads to a release when asked). Needs --allow-actions and approval.",
        {**_ATTACH, "approval": {"type": "string"}},
        attach,
        required=("pr", "evidence", "approval"),
        action=True,
    ),
]
