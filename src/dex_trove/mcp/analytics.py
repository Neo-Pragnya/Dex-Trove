"""Copilot and harness usage analytics, opt-in and local, with every number labelled observed, estimated or unknown.

* ``analytics_consent`` records what may be read: Copilot metrics exports in the project, the GitHub Copilot metrics
  API for an organisation, Claude Code session logs in a folder you name, and ``ananke context eval`` results.
  Nothing is read without it. ``analytics_opt_out`` deletes the consent and every local analytics file.
* ``analytics_sources`` lists which consented sources are reachable now, and what each can and can't tell you.
  Copilot doesn't publish token counts per user or per prompt, so those are always reported as unknown.
* ``analytics_fetch`` saves the organisation's Copilot metrics from the GitHub API (read-only, needs consent).
* ``analytics_normalize`` turns the sources into rows by day, editor, language, session and tool. Prompt and
  response text is never copied: only counts, token totals and tool names.
* ``analytics_estimate`` estimates the tokens graph retrieval would save, from the measured ``saving`` of
  ``ananke context eval`` applied to the observed tokens of file reads. It's labelled as an estimate with its method.
* ``analytics_report`` renders a local HTML page (inline SVG charts, no scripts) and rule-based recommendations.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from dex_trove.mcp import github
from dex_trove.mcp.common import (
    Context,
    ToolError,
    artifact,
    now_iso,
    result,
    write_json,
    write_text,
)
from dex_trove.mcp.server import Tool

NAME = "analytics"
TITLE = "Analytics: Copilot and harness usage, opt-in and local"
CAPABILITIES = (
    "CAP-copilot-analytics-01",
    "CAP-copilot-analytics-02",
    "CAP-copilot-analytics-03",
    "CAP-copilot-analytics-04",
)
INSTRUCTIONS = (
    "Reports how AI assistants are used, from sources the user consented to. Order: analytics_consent (ask the user "
    "which sources), analytics_sources, optionally analytics_fetch, analytics_normalize, analytics_estimate, then "
    "analytics_report. Say 'estimated' and 'unknown' wherever the report does; never claim per-user Copilot token "
    "counts. analytics_opt_out deletes everything collected."
)
SOURCES = ("copilot-export", "copilot-api", "claude-code-sessions", "context-eval")
ORG = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
MAX_SESSION_BYTES = 200_000_000
UNKNOWN = {
    "copilot tokens": "GitHub doesn't publish Copilot token counts per user, prompt or session",
    "copilot cost per request": "billing is per seat or premium request, not per token, in the metrics API",
}


def _consent(ctx: Context) -> dict[str, Any]:
    path = ctx.state / "consent.json"
    if not path.is_file():
        raise ToolError(
            "no consent recorded: ask the user which sources may be read, then call analytics_consent"
        )
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def consent(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    sources = args["sources"]
    bad = [s for s in sources if s not in SOURCES]
    if bad or not sources:
        raise ToolError(f"sources must be some of {', '.join(SOURCES)}")
    record: dict[str, Any] = {
        "schema": "dex-trove/analytics-consent@1",
        "sources": sorted(set(sources)),
        "granted_at": now_iso(),
        "include_prompts": False,
    }
    if "copilot-export" in sources:
        record["exports"] = [ctx.path(p).relative_to(ctx.root).as_posix() for p in args.get("exports") or []]
        if not record["exports"]:
            raise ToolError(
                "copilot-export needs exports: the JSON files saved from the Copilot metrics API or dashboard"
            )
    if "copilot-api" in sources:
        org = args.get("org", "")
        if not ORG.match(org):
            raise ToolError("copilot-api needs org: the GitHub organisation name")
        record["org"] = org
    if "claude-code-sessions" in sources:
        folder = Path(str(args.get("sessions_dir") or "")).expanduser()
        if not folder.is_absolute() or not folder.is_dir():
            raise ToolError(
                "claude-code-sessions needs sessions_dir: an existing folder such as ~/.claude/projects/<project>"
            )
        record["sessions_dir"] = str(folder.resolve())
    if "context-eval" in sources:
        record["context_eval"] = ctx.path(args.get("context_eval") or "").relative_to(ctx.root).as_posix()
    if args.get("include_prompts"):
        raise ToolError(
            "copying prompts isn't supported: analytics only keeps counts, token totals and tool names"
        )
    write_json(ctx.state / "consent.json", record)
    ctx.audit("consent", sources=record["sources"])
    return result(ctx, "ok", consent=record, inputs=args)


def opt_out(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    removed = []
    for folder in (ctx.state, ctx.evidence):
        if folder.exists():
            removed.append(folder.relative_to(ctx.root).as_posix())
            shutil.rmtree(folder)
    ctx.audit("opt-out", removed=removed)
    return result(ctx, "ok", removed=removed, inputs={})


def sources_tool(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    c = _consent(ctx)
    rows = []
    for source in c["sources"]:
        if source == "copilot-export":
            ok = all((ctx.root / p).is_file() for p in c["exports"])
            rows.append(
                {
                    "source": source,
                    "reachable": ok,
                    "files": c["exports"],
                    "observes": ["suggestions", "acceptances", "lines", "chats", "active and engaged users"],
                }
            )
        elif source == "copilot-api":
            token = bool(
                ctx.env.get("GH_TOKEN")
                or ctx.env.get("GITHUB_TOKEN")
                or shutil.which("gh", path=ctx.env.get("PATH"))
            )
            rows.append(
                {
                    "source": source,
                    "reachable": token,
                    "org": c["org"],
                    "needs": "a token with manage_billing:copilot or read:org for the organisation",
                    "observes": ["the same as an export, for the last 28 days"],
                }
            )
        elif source == "claude-code-sessions":
            folder = Path(c["sessions_dir"])
            files = sorted(folder.glob("*.jsonl")) if folder.is_dir() else []
            rows.append(
                {
                    "source": source,
                    "reachable": bool(files),
                    "sessions": len(files),
                    "observes": ["input, output and cache tokens per turn", "tool calls by name"],
                }
            )
        elif source == "context-eval":
            rows.append(
                {
                    "source": source,
                    "reachable": (ctx.root / c["context_eval"]).is_file(),
                    "file": c["context_eval"],
                    "observes": ["measured retrieval recall and token saving on your questions"],
                }
            )
    return result(ctx, "ok", sources=rows, unknown=UNKNOWN, inputs={})


def fetch(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    c = _consent(ctx)
    if "copilot-api" not in c["sources"]:
        raise ToolError(
            "the Copilot metrics API isn't in the consent; add copilot-api with analytics_consent"
        )
    data = github.get(ctx, f"/orgs/{c['org']}/copilot/metrics")
    if not isinstance(data, list):
        raise ToolError("unexpected answer from the Copilot metrics API (expected a list of days)")
    path = write_json(ctx.state / "copilot-api.json", data)
    return result(
        ctx,
        "ok",
        days=len(data),
        artifacts=[artifact(ctx, path, "application/json", sensitivity="confidential")],
        inputs={"org": c["org"]},
    )


def _copilot_rows(days: list[dict[str, Any]], origin: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(day: str, surface: str, metric: str, value: Any, **dims: str) -> None:
        if isinstance(value, int | float) and not isinstance(value, bool):
            rows.append(
                {
                    "date": day,
                    "source": origin,
                    "surface": surface,
                    "metric": metric,
                    "value": value,
                    "kind": "observed",
                    **dims,
                }
            )

    for d in days:
        day = str(d.get("date", ""))
        add(day, "all", "active_users", d.get("total_active_users"))
        add(day, "all", "engaged_users", d.get("total_engaged_users"))
        for editor in (d.get("copilot_ide_code_completions") or {}).get("editors") or []:
            for model in editor.get("models") or []:
                for lang in model.get("languages") or []:
                    dims = {"editor": editor.get("name", ""), "language": lang.get("name", "")}
                    for key in (
                        "total_code_suggestions",
                        "total_code_acceptances",
                        "total_code_lines_suggested",
                        "total_code_lines_accepted",
                        "total_engaged_users",
                    ):
                        add(day, "completions", key.removeprefix("total_"), lang.get(key), **dims)
        for editor in (d.get("copilot_ide_chat") or {}).get("editors") or []:
            for model in editor.get("models") or []:
                for key in (
                    "total_chats",
                    "total_chat_insertion_events",
                    "total_chat_copy_events",
                    "total_engaged_users",
                ):
                    add(
                        day,
                        "ide-chat",
                        key.removeprefix("total_"),
                        model.get(key),
                        editor=editor.get("name", ""),
                    )
        for model in (d.get("copilot_dotcom_chat") or {}).get("models") or []:
            add(day, "dotcom-chat", "chats", model.get("total_chats"))
        for repo in (d.get("copilot_dotcom_pull_requests") or {}).get("repositories") or []:
            for model in repo.get("models") or []:
                add(day, "pull-requests", "pr_summaries_created", model.get("total_pr_summaries_created"))
    return rows


def _session_rows(folder: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Per session: turns, tokens by kind and tool calls by name. Text content is skipped, never stored."""
    sessions: dict[str, dict[str, Any]] = {}
    read_tokens: Counter[str] = Counter()
    for path in sorted(folder.glob("*.jsonl")):
        if path.stat().st_size > MAX_SESSION_BYTES:
            continue
        pending: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            sid = str(event.get("sessionId") or path.stem)
            s = sessions.setdefault(
                sid,
                {
                    "session": sid,
                    "date": str(event.get("timestamp", ""))[:10],
                    "turns": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                    "tools": Counter(),
                },
            )
            raw_message = event.get("message")
            message: dict[str, Any] = raw_message if isinstance(raw_message, dict) else {}
            raw_content = message.get("content")
            content: list[Any] = raw_content if isinstance(raw_content, list) else []
            if event.get("type") == "assistant":
                usage = message.get("usage") or {}
                s["turns"] += 1
                s["input_tokens"] += int(usage.get("input_tokens") or 0)
                s["output_tokens"] += int(usage.get("output_tokens") or 0)
                s["cache_read_tokens"] += int(usage.get("cache_read_input_tokens") or 0)
                s["cache_write_tokens"] += int(usage.get("cache_creation_input_tokens") or 0)
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        s["tools"][str(block.get("name", "?"))] += 1
                        pending[str(block.get("id", ""))] = str(block.get("name", "?"))
            elif event.get("type") == "user":
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        name = pending.get(str(block.get("tool_use_id", "")), "?")
                        size = len(json.dumps(block.get("content", "")))
                        read_tokens[name] += size // 4  # ~4 characters a token: an estimate, labelled as such
    rows = []
    for s in sessions.values():
        if not s["turns"]:
            continue
        rows.append({**s, "tools": dict(sorted(s["tools"].items())), "kind": "observed"})
    rows.sort(key=lambda r: (r["date"], r["session"]))
    return rows, dict(read_tokens)


def normalize(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    c = _consent(ctx)
    copilot: list[dict[str, Any]] = []
    warnings = []
    for rel in c.get("exports", []):
        try:
            data = json.loads((ctx.root / rel).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ToolError(f"{rel}: not a readable JSON export ({exc})") from exc
        if not isinstance(data, list):
            raise ToolError(f"{rel}: expected the Copilot metrics format (a list of days)")
        copilot += _copilot_rows(data, "copilot-export")
    api = ctx.state / "copilot-api.json"
    if "copilot-api" in c["sources"]:
        if api.is_file():
            copilot += _copilot_rows(json.loads(api.read_text(encoding="utf-8")), "copilot-api")
        else:
            warnings.append("copilot-api is consented but not fetched yet; run analytics_fetch")
    sessions: list[dict[str, Any]] = []
    tool_result_tokens: dict[str, int] = {}
    if "claude-code-sessions" in c["sources"]:
        sessions, tool_result_tokens = _session_rows(Path(c["sessions_dir"]))
    data = {
        "schema": "dex-trove/analytics-usage@1",
        "copilot": copilot,
        "sessions": sessions,
        "tool_result_tokens_estimated": tool_result_tokens,
        "unknown": UNKNOWN,
        "prompts_copied": False,
    }
    path = write_json(ctx.state / "usage.json", data)
    return result(
        ctx,
        "ok",
        copilot_rows=len(copilot),
        sessions=len(sessions),
        prompts_copied=False,
        warnings=warnings,
        artifacts=[artifact(ctx, path, "application/json", sensitivity="confidential")],
        inputs={"consent": c["sources"]},
    )


def _usage(ctx: Context) -> dict[str, Any]:
    path = ctx.state / "usage.json"
    if not path.is_file():
        raise ToolError("no normalised usage yet: run analytics_normalize")
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def estimate(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    c = _consent(ctx)
    if "context-eval" not in c["sources"]:
        raise ToolError(
            "context-eval isn't in the consent; save `ananke context eval` output and add it with analytics_consent"
        )
    evaluation = json.loads((ctx.root / c["context_eval"]).read_text(encoding="utf-8"))
    saving, recall = evaluation.get("saving"), evaluation.get("recall")
    if not isinstance(saving, int | float) or not 0 <= saving <= 1:
        raise ToolError(
            f"{c['context_eval']}: no 'saving' between 0 and 1; is it `ananke context eval` output?"
        )
    usage = _usage(ctx)
    reads = sum(
        v
        for k, v in usage["tool_result_tokens_estimated"].items()
        if k in {"Read", "Grep", "Glob", "read_file", "grep_search"}
    )
    observed_input = sum(
        s["input_tokens"] + s["cache_read_tokens"] + s["cache_write_tokens"] for s in usage["sessions"]
    )
    est = {
        "kind": "estimated",
        "method": "measured retrieval saving x tokens returned by file-reading tools (characters / 4)",
        "retrieval_saving": saving,
        "retrieval_recall": recall,
        "file_read_tokens": reads,
        "tokens_saved": round(reads * saving),
        "observed_input_tokens": observed_input,
        "share_of_input": round(reads * saving / observed_input, 3) if observed_input else None,
        "caveats": [
            "recall below 1 means some answers would need a follow-up read",
            "tool results stay in context for later turns, so the real saving can be larger",
        ],
    }
    data = {**usage, "estimate": est}
    write_json(ctx.state / "usage.json", data)
    return result(ctx, "ok", estimate=est, inputs={"eval": c["context_eval"]})


def _bars(
    title: str,
    items: list[tuple[str, int]] | list[tuple[str, float]],
    *,
    dashed: bool = False,
    unit: str = "",
) -> str:
    if not items:
        return f"<h3>{html.escape(title)}</h3><p class=muted>No data.</p>"
    top = max(v for _, v in items) or 1
    h = 26 * len(items) + 10
    rows = []
    for i, (label, value) in enumerate(items):
        w = max(1, round(360 * value / top))
        style = (
            'fill="none" stroke="currentColor" stroke-dasharray="4 3"' if dashed else 'fill="currentColor"'
        )
        rows.append(
            f'<text x="0" y="{26 * i + 18}" font-size="12">{html.escape(label[:28])}</text>'
            f'<rect x="190" y="{26 * i + 6}" width="{w}" height="16" rx="3" {style}/>'
            f'<text x="{196 + w}" y="{26 * i + 18}" font-size="12">{value:,.4g}{html.escape(unit)}</text>'
        )
    return (
        f'<h3>{html.escape(title)}</h3><svg role=img aria-label="{html.escape(title)}" viewBox="0 0 640 {h}" '
        f'width="100%" class="{"est" if dashed else "obs"}">{"".join(rows)}</svg>'
    )


def recommendations(usage: dict[str, Any]) -> list[str]:
    out = []
    by_lang: dict[str, Counter[str]] = defaultdict(Counter)
    for r in usage["copilot"]:
        if r["surface"] == "completions":
            by_lang[r.get("language", "?")][r["metric"]] += r["value"]
    for lang, m in sorted(by_lang.items()):
        if m["code_suggestions"] >= 100 and m["code_acceptances"] / m["code_suggestions"] < 0.2:
            out.append(
                f"Completions in {lang} are accepted {m['code_acceptances'] / m['code_suggestions']:.0%} of the time: "
                "check that the repository's instructions and examples cover it."
            )
    tools: Counter[str] = Counter()
    for s in usage["sessions"]:
        tools.update(s["tools"])
    reads = tools["Read"] + tools["Grep"] + tools["Glob"]
    if reads and reads / max(1, sum(tools.values())) > 0.4:
        out.append(
            f"{reads} of {sum(tools.values())} tool calls read files: try `ananke context ask` or outline/symbol first."
        )
    cache = sum(s["cache_read_tokens"] for s in usage["sessions"])
    fresh = sum(s["input_tokens"] + s["cache_write_tokens"] for s in usage["sessions"])
    if fresh and cache / (cache + fresh) < 0.5:
        out.append(
            f"Only {cache / (cache + fresh):.0%} of input came from the prompt cache: keep sessions on one task longer."
        )
    est = usage.get("estimate")
    if est and est["tokens_saved"]:
        out.append(
            f"Graph retrieval would save about {est['tokens_saved']:,} tokens of file reads (estimated, "
            f"recall {est['retrieval_recall']})."
        )
    return out or ["Nothing stands out in this data."]


def report(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    usage = _usage(ctx)
    acc: dict[str, Counter[str]] = defaultdict(Counter)
    chats: Counter[str] = Counter()
    for r in usage["copilot"]:
        if r["surface"] == "completions":
            acc[r.get("language", "?")][r["metric"]] += r["value"]
        if r["surface"] == "ide-chat" and r["metric"] == "chats":
            chats[r.get("editor", "?")] += r["value"]
    rates = sorted(
        (
            (lang, 100 * m["code_acceptances"] / m["code_suggestions"])
            for lang, m in acc.items()
            if m["code_suggestions"]
        ),
        key=lambda x: -x[1],
    )
    sessions = usage["sessions"][-15:]
    tools: Counter[str] = Counter()
    for s in usage["sessions"]:
        tools.update(s["tools"])
    est = usage.get("estimate")
    recs = recommendations(usage)
    parts = [
        '<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">',
        "<meta http-equiv=Content-Security-Policy content=\"default-src 'none'; style-src 'unsafe-inline'\">",
        "<title>Assistant usage</title><style>:root{--fg:#1d2330;--bg:#fff;--muted:#5b6475;--obs:#2f6fdb;--est:#c06a00}"
        "@media (prefers-color-scheme:dark){:root{--fg:#e7eaf0;--bg:#14171d;--muted:#9aa3b2;--obs:#7aa7ff;--est:#ffb257}}"
        "body{font:15px/1.5 system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 16px;color:var(--fg);background:var(--bg)}"
        "svg text{fill:var(--fg)}.obs{color:var(--obs)}.est{color:var(--est)}.muted{color:var(--muted)}"
        "table{border-collapse:collapse}td,th{padding:.25rem .6rem;border-bottom:1px solid #8884;text-align:left}</style></head><body>",
        "<h1>Assistant usage</h1>",
        "<p class=muted>Solid bars are <strong>observed</strong>; dashed bars are <strong>estimated</strong>. "
        "No prompt or response text was read into this report.</p>",
        _bars("Copilot completion acceptance by language (observed, %)", rates[:12], unit="%"),
        _bars("Copilot IDE chats by editor (observed)", sorted(chats.items(), key=lambda x: -x[1])[:10]),
        _bars(
            "Tokens per session, input + cache + output (observed)",
            [
                (
                    s["session"][:8] + " " + s["date"],
                    s["input_tokens"] + s["cache_read_tokens"] + s["cache_write_tokens"] + s["output_tokens"],
                )
                for s in sessions
            ],
        ),
        _bars("Tool calls (observed)", tools.most_common(10)),
    ]
    if est:
        parts.append(
            _bars(
                "File-read tokens and graph retrieval (estimated)",
                [("file reads now", est["file_read_tokens"]), ("saved by retrieval", est["tokens_saved"])],
                dashed=True,
            )
        )
        parts.append(
            f"<p class=muted>Method: {html.escape(est['method'])}. Measured saving {est['retrieval_saving']}, recall "
            f"{est['retrieval_recall']}.</p>"
        )
    parts.append(
        "<h2>Unknown</h2><table>"
        + "".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>" for k, v in UNKNOWN.items())
        + "</table>"
    )
    parts.append(
        "<h2>Recommendations</h2><ul>"
        + "".join(f"<li>{html.escape(r)}</li>" for r in recs)
        + "</ul></body></html>"
    )
    page = write_text(ctx.evidence / "usage-report.html", "\n".join(parts) + "\n")
    return result(
        ctx,
        "ok",
        recommendations=recs,
        labels={"observed": True, "estimated": bool(est), "unknown": list(UNKNOWN)},
        artifacts=[artifact(ctx, page, "text/html", sensitivity="confidential")],
        inputs={},
    )


TOOLS = [
    Tool(
        "analytics_consent",
        "Records which usage sources may be read. Nothing is read before this. Prompts are never copied.",
        {
            "sources": {"type": "array", "items": {"type": "string"}, "description": ", ".join(SOURCES)},
            "exports": {"type": "array", "items": {"type": "string"}},
            "org": {"type": "string"},
            "sessions_dir": {"type": "string"},
            "context_eval": {"type": "string"},
            "include_prompts": {"type": "boolean"},
        },
        consent,
        required=("sources",),
        writes=True,
    ),
    Tool(
        "analytics_opt_out", "Deletes the consent and every local analytics file.", {}, opt_out, writes=True
    ),
    Tool(
        "analytics_sources",
        "Which consented sources are reachable, what they observe, and what stays unknown.",
        {},
        sources_tool,
    ),
    Tool(
        "analytics_fetch",
        "Saves the organisation's Copilot metrics from the GitHub API (read-only, needs consent).",
        {},
        fetch,
        writes=True,
    ),
    Tool(
        "analytics_normalize",
        "Usage rows by day, editor, language, session and tool, without prompt text.",
        {},
        normalize,
        writes=True,
    ),
    Tool(
        "analytics_estimate",
        "Estimated token saving from graph retrieval, using the measured saving from ananke context eval.",
        {},
        estimate,
        writes=True,
    ),
    Tool(
        "analytics_report",
        "A local HTML report with observed and estimated charts, unknowns and recommendations.",
        {},
        report,
        writes=True,
    ),
]
