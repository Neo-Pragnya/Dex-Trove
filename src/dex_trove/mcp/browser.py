"""A browser lab for debugging a web UI with Playwright, kept outside Dex: Dex writes files and reads traces only.

* ``browser_lab_create`` writes an isolated Playwright project (``browser-lab/<name>/``) pinned to an exact
  ``@playwright/test`` version: trace and screenshots on, one worker, no retries, and read-only checks (each page
  loads, answers below 400, and logs no console errors). Screenshots mask the selectors you call sensitive. The base
  URL must be on this machine unless ``.dex/browser.json`` lists the host under ``test_hosts``; production is never a
  target. No browser or Node package ever enters Dex.
* ``browser_lab_run`` installs and runs it (``npm install``, ``npx playwright install chromium``, ``npx playwright
  test``). It downloads software, so it needs ``--allow-actions`` and the approval digest from the create step.
* ``browser_trace`` reads a Playwright trace zip: actions with their outcome, console errors, page errors, failed
  requests, screenshots and DOM snapshots. The zip is checked first (size, ratio, paths).
* ``browser_map`` maps failing selectors and pages to frontend source: test ids, ids, classes, roles, labels and
  text, and the route definitions that serve the failing URL.
* ``browser_evidence`` writes a redacted evidence bundle and SARIF under ``dex-evidence/browser/`` for Ananke:
  cookies, authorization headers and secrets in URLs are removed, and screenshots are copied only when asked.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.parse
import zipfile
from pathlib import Path
from typing import Any

from dex_trove.mcp.common import (
    Context,
    ToolError,
    approval_for,
    artifact,
    check_url,
    finding,
    is_loopback,
    redact,
    require_approval,
    result,
    sha256_file,
    stable_digest,
    write_json,
    write_sarif,
    write_text,
)
from dex_trove.mcp.server import Tool

NAME = "browser"
TITLE = "Browser lab: Playwright traces mapped to source"
CAPABILITIES = (
    "CAP-browser-debugging-01",
    "CAP-browser-debugging-02",
    "CAP-browser-debugging-03",
    "CAP-browser-debugging-04",
)
INSTRUCTIONS = (
    "Debugs a web UI with Playwright without putting a browser in Dex. Order: browser_lab_create (an isolated, "
    "read-only test project against a local or listed test URL; returns an approval digest for running it), "
    "browser_lab_run after the user agrees (needs --allow-actions), or bring an existing trace.zip; then "
    "browser_trace, browser_map to find the source behind failing selectors and routes, and browser_evidence for a "
    "redacted bundle. Never point the lab at production."
)
PLAYWRIGHT_VERSION = "1.48.2"
CHANNELS = ("chromium", "chrome", "msedge")
LAB_DIR = "browser-lab"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
MAX_ZIP_ENTRIES = 20_000
MAX_UNZIPPED = 1_000_000_000
MAX_RATIO = 200
FRONTEND = (".tsx", ".jsx", ".ts", ".js", ".vue", ".svelte", ".html", ".astro", ".mdx")
SKIP_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        "dist",
        "build",
        ".next",
        ".nuxt",
        ".svelte-kit",
        "coverage",
        LAB_DIR,
        "dex-evidence",
        ".dex",
        ".venv",
        "venv",
        "__pycache__",
    }
)


# ── Lab ─────────────────────────────────────────────────────────────────────


def _base_url(ctx: Context, value: str) -> str:
    parts = check_url(value, what="base_url")
    host = parts.hostname or ""
    allowed = {str(h).lower() for h in ctx.config(NAME).get("test_hosts", [])}
    if not is_loopback(host) and host.lower() not in allowed:
        raise ToolError(
            f"{host} isn't on this machine or listed in .dex/browser.json test_hosts. The lab only runs "
            "against local or named test environments, never production."
        )
    return value.rstrip("/")


def _pages(pages: list[str]) -> list[str]:
    out = []
    for page in pages or ["/"]:
        if not isinstance(page, str) or not page.startswith("/") or "//" in page or len(page) > 300:
            raise ToolError(
                f"page {page!r} must be a path starting with / (the base URL is given separately)"
            )
        out.append(page)
    return out


def _selectors(values: list[str]) -> list[str]:
    for v in values:
        if not isinstance(v, str) or not v or len(v) > 200 or "`" in v or "\n" in v:
            raise ToolError(f"sensitive selector {v!r} isn't a plain CSS selector")
    return values


def _spec(pages: list[str], sensitive: list[str]) -> str:
    masks = ", ".join(f"page.locator({json.dumps(s)})" for s in sensitive)
    tests = []
    for p in pages:
        tests.append(f"""
test({json.dumps("loads " + p)}, async ({{ page }}) => {{
  const errors: string[] = [];
  // a missing favicon is the browser's request, not the page's error
  page.on('console', (m) => {{ if (m.type() === 'error' && !m.location().url.endsWith('/favicon.ico')) errors.push(m.text()); }});
  page.on('pageerror', (e) => errors.push(String(e)));
  const response = await page.goto({json.dumps(p)});
  expect(response, 'the page answered').not.toBeNull();
  expect(response!.status(), 'HTTP status').toBeLessThan(400);
  await page.waitForLoadState('networkidle');
  await page.screenshot({{ path: test.info().outputPath('page.png'), fullPage: true, mask: [{masks}] }});
  expect(errors, 'console errors').toEqual([]);
}});""")
    return (
        "// Generated by dex-trove browser_lab_create: read-only checks only (navigate, look, screenshot).\n"
        "// Don't add clicks that submit, delete or pay here: the lab may run against shared test environments.\n"
        "import { test, expect } from '@playwright/test';\n" + "\n".join(tests) + "\n"
    )


def _lab_plan(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    if not NAME_RE.match(name):
        raise ToolError("name must be lowercase letters, digits and hyphens")
    base = _base_url(ctx, args["base_url"])
    pages = _pages(args.get("pages") or [])
    sensitive = _selectors(args.get("sensitive_selectors") or [])
    channel = args.get("channel") or "chromium"
    if channel not in CHANNELS:
        raise ToolError(f"channel must be one of {', '.join(CHANNELS)}")
    device = "...devices['Desktop Chrome']" + ("" if channel == "chromium" else f", channel: '{channel}'")
    folder = f"{LAB_DIR}/{name}"
    files = {
        "package.json": json.dumps(
            {
                "name": f"browser-lab-{name}",
                "private": True,
                "scripts": {"test": "playwright test"},
                "devDependencies": {"@playwright/test": PLAYWRIGHT_VERSION},
            },
            indent=2,
        )
        + "\n",
        "playwright.config.ts": (
            "import { defineConfig, devices } from '@playwright/test';\n"
            "export default defineConfig({\n  testDir: './tests',\n  retries: 0,\n  workers: 1,\n  timeout: 30_000,\n"
            "  reporter: [['list'], ['json', { outputFile: 'results.json' }]],\n"
            f"  use: {{ baseURL: {json.dumps(base)}, trace: 'on', screenshot: 'only-on-failure', video: 'off' }},\n"
            f"  projects: [{{ name: '{channel}', use: {{ {device} }} }}],\n}});\n"
        ),
        "tests/pages.spec.ts": _spec(pages, sensitive),
        ".gitignore": "node_modules/\ntest-results/\nplaywright-report/\nresults.json\n",
    }
    return {
        "action": "browser.lab-run",
        "folder": folder,
        "base_url": base,
        "pages": pages,
        "sensitive_selectors": sensitive,
        "playwright": PLAYWRIGHT_VERSION,
        "channel": channel,
        "files": {k: stable_digest(v) for k, v in files.items()},
        "commands": [
            "npm install --no-audit --no-fund",
            *(["npx playwright install chromium"] if channel == "chromium" else []),
            "npx playwright test",
        ],
        "_contents": files,
    }


def lab_create(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    plan = _lab_plan(ctx, args)
    contents = plan.pop("_contents")
    folder = ctx.path(plan["folder"], must_exist=False)
    for rel, text in contents.items():
        target = folder / rel
        if target.exists() and target.read_text(encoding="utf-8") != text and not args.get("overwrite"):
            raise ToolError(f"{plan['folder']}/{rel} exists and differs; pass overwrite to replace the lab")
        write_text(target, text)
    return result(
        ctx,
        "created",
        plan=plan,
        approval=approval_for(plan),
        actions_enabled=ctx.allow_actions,
        artifacts=[artifact(ctx, folder / rel, "text/plain") for rel in sorted(contents)],
        warnings=[
            "Running the lab downloads Playwright from npm"
            + (
                " and Chromium from the Playwright CDN."
                if plan["channel"] == "chromium"
                else f"; it uses the installed {plan['channel']}."
            )
        ],
        inputs=args,
    )


def lab_run(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    plan = _lab_plan(ctx, args)
    plan.pop("_contents")
    require_approval(ctx, plan, args.get("approval"), action="browser.lab-run")
    folder = ctx.path(plan["folder"])
    npm, npx = shutil.which("npm", path=ctx.env.get("PATH")), shutil.which("npx", path=ctx.env.get("PATH"))
    if not npm or not npx:
        raise ToolError("Node.js (npm and npx) isn't installed or isn't on PATH")
    steps = []
    commands = [[npm, "install", "--no-audit", "--no-fund"], [npx, "playwright", "test"]]
    if plan["channel"] == "chromium":
        commands.insert(1, [npx, "playwright", "install", "chromium"])
    for argv in commands:
        done = subprocess.run(
            argv, cwd=folder, capture_output=True, text=True, timeout=1800, check=False, env=dict(ctx.env)
        )  # noqa: S603
        steps.append(
            {
                "command": " ".join(Path(argv[0]).name if i == 0 else a for i, a in enumerate(argv)),
                "exit": done.returncode,
                "tail": redact((done.stdout + done.stderr)[-1500:]),
            }
        )
        if done.returncode != 0 and argv[-1] != "test":
            break
    traces = sorted(p.relative_to(ctx.root).as_posix() for p in folder.glob("test-results/**/trace.zip"))
    ctx.audit("ran", action="browser.lab-run", folder=plan["folder"], exit=steps[-1]["exit"])
    status = "passed" if steps[-1]["exit"] == 0 and len(steps) == len(commands) else "failed"
    return result(ctx, status, steps=steps, traces=traces, inputs=args)


# ── Traces ──────────────────────────────────────────────────────────────────


def _open_zip(ctx: Context, value: str) -> zipfile.ZipFile:
    path = ctx.path(value)
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ToolError(f"{value}: not a zip file (a Playwright trace is trace.zip)") from exc
    infos = zf.infolist()
    if len(infos) > MAX_ZIP_ENTRIES:
        raise ToolError(f"{value}: more than {MAX_ZIP_ENTRIES} entries, refused")
    total = sum(i.file_size for i in infos)
    packed = max(1, sum(i.compress_size for i in infos))
    if total > MAX_UNZIPPED or total / packed > MAX_RATIO:
        raise ToolError(
            f"{value}: unpacks to {total} bytes (ratio {total // packed}), refused as a possible zip bomb"
        )
    if any(i.filename.startswith("/") or ".." in Path(i.filename).parts for i in infos):
        raise ToolError(f"{value}: has entries outside the archive, refused")
    if not any(i.filename.endswith(".trace") for i in infos):
        raise ToolError(f"{value}: no .trace file inside; is this a Playwright trace?")
    return zf


def _jsonl(zf: zipfile.ZipFile, suffix: str) -> list[dict[str, Any]]:
    events = []
    for name in sorted(n for n in zf.namelist() if n.endswith(suffix)):
        for line in zf.read(name).decode("utf-8", "replace").splitlines():
            if line.strip():
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if isinstance(item, dict):
                    events.append(item)
    return events


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _error_text(value: Any) -> str:
    if isinstance(value, dict):
        inner = value.get("error") if isinstance(value.get("error"), dict) else value
        return ANSI.sub("", str((inner or {}).get("message") or (inner or {}).get("value") or ""))
    return ANSI.sub("", str(value or ""))


def _headers(value: Any) -> dict[str, str]:
    if isinstance(value, list):
        return {str(h.get("name", "")).lower(): str(h.get("value", "")) for h in value if isinstance(h, dict)}
    return {}


def parse_trace(zf: zipfile.ZipFile) -> dict[str, Any]:
    events = _jsonl(zf, ".trace")
    network = _jsonl(zf, ".network")
    version = next((e.get("version") for e in events if e.get("type") == "context-options"), None)
    calls: dict[str, dict[str, Any]] = {}
    console, page_errors, screenshots, snapshots, urls = [], [], [], 0, []
    for e in events:
        kind = e.get("type")
        if kind == "before":
            params = e.get("params") or {}
            calls[str(e.get("callId"))] = {
                "call": str(e.get("callId")),
                "api": e.get("apiName") or e.get("title") or f"{e.get('class', '')}.{e.get('method', '')}",
                "selector": params.get("selector", ""),
                "url": params.get("url", ""),
                "status": "ok",
                "error": "",
                "start": e.get("startTime", 0),
            }
            if params.get("url"):
                urls.append(params["url"])
        elif kind == "after" and str(e.get("callId")) in calls:
            err = _error_text(e.get("error"))
            if err:
                calls[str(e.get("callId"))].update(status="failed", error=err)
        elif kind == "console":
            level = e.get("messageType") or (e.get("params") or {}).get("type", "")
            if level in {"error", "warning"}:
                loc = e.get("location") or {}
                console.append(
                    {
                        "level": level,
                        "text": e.get("text", ""),
                        "url": loc.get("url", ""),
                        "line": loc.get("lineNumber"),
                    }
                )
        elif kind == "event" and e.get("method") == "pageError":
            page_errors.append(_error_text((e.get("params") or {}).get("error")))
        elif kind == "screencast-frame":
            screenshots.append(str(e.get("sha1", "")))
        elif kind == "frame-snapshot":
            snapshots += 1
    requests = []
    for n in network:
        snap = n.get("snapshot") or {}
        req, resp = snap.get("request") or {}, snap.get("response") or {}
        status = int(resp.get("status") or 0)
        requests.append(
            {
                "method": req.get("method", ""),
                "url": req.get("url", ""),
                "status": status,
                "failed": status >= 400 or status == 0 and bool(snap.get("_failureText")),
                "failure": snap.get("_failureText", ""),
                "content_type": _headers(resp.get("headers")).get("content-type", ""),
            }
        )
    actions = sorted(calls.values(), key=lambda c: (c["start"], c["call"]))
    for a in actions:
        a.pop("start")
    return {
        "format_version": version,
        "actions": actions,
        "failed_actions": [a for a in actions if a["status"] == "failed"],
        "console": console,
        "page_errors": page_errors,
        "requests": requests,
        "failed_requests": [r for r in requests if r["failed"]],
        "screenshots": screenshots,
        "dom_snapshots": snapshots,
        "pages": list(dict.fromkeys(urls)),
    }


def trace_tool(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    with _open_zip(ctx, args["trace"]) as zf:
        data = parse_trace(zf)
    summary = {k: len(v) if isinstance(v, list) else v for k, v in data.items() if k not in {"pages"}}
    warnings = (
        []
        if data["format_version"]
        else ["no context-options event: the trace format wasn't recognised fully"]
    )
    return result(
        ctx,
        "failed" if data["failed_actions"] or data["page_errors"] else "ok",
        summary=summary,
        failed_actions=data["failed_actions"],
        console=data["console"][:50],
        page_errors=data["page_errors"][:20],
        failed_requests=[{**r, "url": redact(r["url"])} for r in data["failed_requests"][:50]],
        pages=data["pages"],
        warnings=warnings,
        inputs={"trace": args["trace"]},
    )


# ── Source mapping ──────────────────────────────────────────────────────────


def selector_targets(selector: str) -> list[tuple[str, str]]:
    """What a Playwright selector looks for: (kind, value) pairs such as ("testid", "save") or ("text", "Sign in")."""
    found: list[tuple[str, str]] = []
    for part in re.split(r"\s*>>\s*", selector or ""):
        part = part.strip()
        patterns = [
            (r'internal:testid=\[([\w-]+)=["\']([^"\']+)["\']', "testid"),
            (r'\[(data-testid|data-test|data-test-id|data-cy|data-qa)=["\']?([^"\'\]]+)["\']?\]', "testid"),
            (r'internal:role=(\w+)(?:\[name=["\']([^"\']+)["\'])?', "role"),
            (r'internal:(?:text|has-text)=["\']([^"\']+)["\']', "text"),
            (r'^text=["\']?([^"\']+)["\']?$', "text"),
            (r'internal:label=["\']([^"\']+)["\']', "label"),
            (r'internal:attr=\[placeholder=["\']([^"\']+)["\']', "placeholder"),
            (r"#([A-Za-z][\w-]*)", "id"),
            (r"\.([A-Za-z][\w-]*)", "class"),
        ]
        for pattern, kind in patterns:
            for m in re.finditer(pattern, part):
                if kind == "testid":
                    found.append(("testid", m.group(2)))
                elif kind == "role":
                    found.append(("role", m.group(1)))
                    if m.group(2):
                        found.append(("text", m.group(2)))
                else:
                    found.append((kind, m.group(1)))
            if (
                found
                and kind in {"testid", "role", "text", "label", "placeholder"}
                and part.startswith("internal:")
            ):
                break
    return list(dict.fromkeys(found))


def _source_patterns(kind: str, value: str) -> list[re.Pattern[str]]:
    v = re.escape(value)
    return {
        "testid": [re.compile(rf"""data-(?:testid|test|test-id|cy|qa)\s*=\s*\{{?\s*["'`]{v}["'`]""")],
        "id": [re.compile(rf"""\bid\s*=\s*\{{?\s*["'`]{v}["'`]""")],
        "class": [re.compile(rf"""class(?:Name)?\s*=\s*\{{?\s*["'`][^"'`]*\b{v}\b""")],
        "text": [re.compile(rf">\s*{v}\s*<"), re.compile(rf"""["'`]{v}["'`]""")],
        "label": [re.compile(rf"""aria-label\s*=\s*["'`]{v}["'`]"""), re.compile(rf">\s*{v}\s*<")],
        "placeholder": [re.compile(rf"""placeholder\s*=\s*\{{?\s*["'`]{v}["'`]""")],
        "role": [re.compile(rf"""role\s*=\s*["'`]{v}["'`]"""), re.compile(rf"<{v}\b")],
    }.get(kind, [])


def _frontend_files(ctx: Context, paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for start in [ctx.path(p) for p in paths] if paths else [ctx.root]:
        for folder, dirs, names in os.walk(start):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
            out += [
                Path(folder) / n
                for n in sorted(names)
                if n.endswith(FRONTEND) and ".spec." not in n and ".test." not in n
            ]
            if len(out) > 20_000:
                return out
    return out


def _route_matches(files: list[Path], root: Path, url_path: str) -> list[dict[str, Any]]:
    segs = [s for s in url_path.strip("/").split("/") if s]
    hits = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        file_route = re.search(
            r"(?:^|/)(?:pages|app|routes)/(.*?)(?:/(?:page|\+page|index))?\.(?:tsx|jsx|ts|js|vue|svelte|astro|mdx)$",
            rel,
        )
        if file_route:
            parts = [
                p
                for p in file_route.group(1).split("/")
                if p and p not in {"index", "page", "+page"} and not p.startswith("(")
            ]
            if len(parts) == len(segs) and all(
                p == s or re.fullmatch(r"\[\.{0,3}\w+\]|:\w+", p) for p, s in zip(parts, segs, strict=True)
            ):
                hits.append({"file": rel, "line": 1, "kind": "file-route"})
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in re.finditer(r"""\bpath\s*[:=]\s*\{?\s*["'`](/[^"'`]*)["'`]""", text):
            parts = [p for p in m.group(1).strip("/").split("/") if p]
            if len(parts) == len(segs) and all(
                p == s or p.startswith(":") or re.fullmatch(r"\[\w+\]", p)
                for p, s in zip(parts, segs, strict=True)
            ):
                hits.append(
                    {
                        "file": rel,
                        "line": text.count("\n", 0, m.start()) + 1,
                        "kind": "route",
                        "route": m.group(1),
                    }
                )
    return hits


def map_tool(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    selectors = list(args.get("selectors") or [])
    pages = list(args.get("urls") or [])
    if args.get("trace"):
        with _open_zip(ctx, args["trace"]) as zf:
            data = parse_trace(zf)
        selectors += [a["selector"] for a in data["failed_actions"] if a["selector"]]
        pages += data["pages"]
    if not selectors and not pages:
        raise ToolError("nothing to map: pass a trace with failed actions, or selectors and urls")
    files = _frontend_files(ctx, args.get("paths") or [])
    texts = {f: f.read_text(encoding="utf-8", errors="replace") for f in files}
    mapped, findings = [], []
    for selector in dict.fromkeys(selectors):
        matches: list[dict[str, Any]] = []
        for kind, value in selector_targets(selector):
            for f, text in texts.items():
                for pattern in _source_patterns(kind, value):
                    for m in pattern.finditer(text):
                        matches.append(
                            {
                                "file": f.relative_to(ctx.root).as_posix(),
                                "line": text.count("\n", 0, m.start()) + 1,
                                "kind": kind,
                                "value": value,
                            }
                        )
        matches = [dict(t) for t in dict.fromkeys(tuple(sorted(m.items())) for m in matches)][:20]
        mapped.append({"selector": selector, "targets": selector_targets(selector), "matches": matches})
        if not matches:
            findings.append(
                finding(
                    "warning",
                    f"selector {selector!r} matches nothing in the frontend source; it may have been "
                    "renamed or be rendered from data",
                    rule="browser.selector-unmapped",
                    status="inferred",
                    remediation="add a stable data-testid to the element and use getByTestId",
                )
            )
        else:
            first = matches[0]
            findings.append(
                finding(
                    "note",
                    f"selector {selector!r} is defined here",
                    rule="browser.selector-source",
                    uri=first["file"],
                    line=first["line"],
                    status="inferred",
                )
            )
    routes = []
    for url in dict.fromkeys(pages):
        path = urllib.parse.urlsplit(url).path or "/"
        routes.append(
            {"url": redact(url), "path": path, "matches": _route_matches(files, ctx.root, path)[:10]}
        )
    return result(ctx, "ok", selectors=mapped, routes=routes, findings=findings, inputs=args)


# ── Evidence ────────────────────────────────────────────────────────────────


def _redact_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.urlencode(
        [(k, "[REDACTED]") for k, _ in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)]
    )
    return redact(urllib.parse.urlunsplit((parts.scheme, parts.hostname or "", parts.path, query, "")))


def evidence_tool(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    trace = args["trace"]
    stem = re.sub(r"[^a-z0-9]+", "-", Path(trace).parent.name.lower() + "-" + Path(trace).stem.lower()).strip(
        "-"
    )
    out = ctx.evidence / stem
    with _open_zip(ctx, trace) as zf:
        data = parse_trace(zf)
        shots = []
        if args.get("include_screenshots"):
            for sha in data["screenshots"][-int(args.get("max_screenshots", 5)) :]:
                name = f"resources/{sha}"
                if sha and name in zf.namelist():
                    target = out / "screenshots" / Path(sha).name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(zf.read(name))
                    shots.append(artifact(ctx, target, "image/jpeg", sensitivity="confidential"))
    findings = [
        finding(
            "error",
            f"{a['api']} failed: {redact(a['error'])[:300]}",
            rule="browser.action-failed",
            uri=_redact_url(a["url"]) if a["url"] else "",
            status="observed",
        )
        for a in data["failed_actions"]
    ]
    findings += [
        finding("error", f"page error: {redact(e)[:300]}", rule="browser.page-error")
        for e in data["page_errors"]
    ]
    findings += [
        finding(
            "warning" if c["level"] == "warning" else "error",
            f"console {c['level']}: {redact(c['text'])[:300]}",
            rule="browser.console",
            uri=_redact_url(c["url"]) if c["url"] else "",
            line=c["line"],
        )
        for c in data["console"]
    ]
    findings += [
        finding(
            "error",
            f"{r['method']} {_redact_url(r['url'])} answered {r['status'] or r['failure']}",
            rule="browser.request-failed",
        )
        for r in data["failed_requests"]
    ]
    bundle = {
        "schema": "dex-trove/browser-evidence@1",
        "trace": trace,
        "trace_sha256": sha256_file(ctx.path(trace)),
        "run_id": args.get("run_id", ""),
        "format_version": data["format_version"],
        "actions": [
            {**a, "url": _redact_url(a["url"]) if a["url"] else "", "error": redact(a["error"])}
            for a in data["actions"]
        ],
        "console": [
            {**c, "text": redact(c["text"]), "url": _redact_url(c["url"]) if c["url"] else ""}
            for c in data["console"]
        ],
        "page_errors": [redact(e) for e in data["page_errors"]],
        "requests": [
            {
                "method": r["method"],
                "url": _redact_url(r["url"]),
                "status": r["status"],
                "content_type": r["content_type"],
            }
            for r in data["requests"]
        ],
        "screenshots": {"in_trace": len(data["screenshots"]), "copied": [s["path"] for s in shots]},
        "dom_snapshots": data["dom_snapshots"],
        "redaction": "query values, cookies, authorization headers and secret-shaped text removed; request and response "
        "headers other than content-type dropped; screenshot pixels are only masked where the lab masked them",
    }
    path = write_json(out / "evidence.json", bundle)
    artifacts = [artifact(ctx, path, "application/json", schema="dex-trove/browser-evidence@1"), *shots]
    if findings:
        artifacts.append(
            artifact(
                ctx,
                write_sarif(ctx, f"{stem}/browser", findings, tool="dex-browser"),
                "application/sarif+json",
            )
        )
    warnings = (
        ["screenshots may show personal data the masks didn't cover; review before sharing"] if shots else []
    )
    return result(
        ctx,
        "failed" if any(f["severity"] == "error" for f in findings) else "ok",
        findings=findings,
        artifacts=artifacts,
        warnings=warnings,
        inputs={"trace": trace, "run_id": args.get("run_id", "")},
    )


_LAB: dict[str, dict[str, Any]] = {
    "name": {"type": "string", "description": "Lab name: lowercase letters, digits, hyphens"},
    "base_url": {
        "type": "string",
        "description": "http://localhost:3000 or a host in .dex/browser.json test_hosts",
    },
    "pages": {"type": "array", "items": {"type": "string"}, "description": "Paths to check, default ['/']"},
    "channel": {
        "type": "string",
        "enum": list(CHANNELS),
        "description": "chromium (downloaded) or an installed chrome or msedge",
    },
    "sensitive_selectors": {
        "type": "array",
        "items": {"type": "string"},
        "description": "CSS selectors masked in screenshots",
    },
}
_TRACE = {"type": "string", "description": "A Playwright trace.zip in the project"}

TOOLS = [
    Tool(
        "browser_lab_create",
        "Writes an isolated, read-only Playwright project pinned to an exact version, and the approval "
        "digest for running it. Installs and runs nothing.",
        {**_LAB, "overwrite": {"type": "boolean"}},
        lab_create,
        required=("name", "base_url"),
        writes=True,
    ),
    Tool(
        "browser_lab_run",
        "Installs Playwright and Chromium into the lab and runs it. Downloads software: needs --allow-actions "
        "and the approval digest the user accepted.",
        {**_LAB, "approval": {"type": "string"}},
        lab_run,
        required=("name", "base_url", "approval"),
        action=True,
    ),
    Tool(
        "browser_trace",
        "Actions, failures, console and page errors, failed requests, screenshots and DOM snapshots in a trace.",
        {"trace": _TRACE},
        trace_tool,
        required=("trace",),
    ),
    Tool(
        "browser_map",
        "Maps failing selectors and pages (from a trace, or given) to frontend source and route definitions.",
        {
            "trace": _TRACE,
            "selectors": {"type": "array", "items": {"type": "string"}},
            "urls": {"type": "array", "items": {"type": "string"}},
            "paths": {"type": "array", "items": {"type": "string"}},
        },
        map_tool,
    ),
    Tool(
        "browser_evidence",
        "Writes a redacted evidence bundle and SARIF for a trace; screenshots only when asked.",
        {
            "trace": _TRACE,
            "run_id": {"type": "string", "description": "Ananke run this evidence belongs to"},
            "include_screenshots": {"type": "boolean"},
            "max_screenshots": {"type": "integer"},
        },
        evidence_tool,
        required=("trace",),
        writes=True,
    ),
]
