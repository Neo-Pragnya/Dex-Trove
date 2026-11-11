"""Browser lab: lab files, refusals, trace parsing (shapes from a real Playwright 1.48 trace), mapping, evidence."""

from __future__ import annotations

import json
import secrets
import zipfile
from pathlib import Path

import pytest

from dex_trove.mcp import browser
from dex_trove.mcp.common import Context, ToolError
from dex_trove.mcp.server import Server

PAGE = "page@a2830"
# Fake credentials made at run time: the tests prove they're redacted, and nothing secret-shaped is committed.
CONSOLE_TOKEN = secrets.token_hex(8)
QUERY_TOKEN = secrets.token_hex(8)
COOKIE = secrets.token_hex(8)
BEARER = secrets.token_hex(12)
SESSION = secrets.token_hex(6)


def trace_zip(path: Path, *, broken: bool = True) -> Path:
    """A trace laid out like Playwright 1.48 writes it: test.trace, 0-trace.trace, 0-trace.network, resources/."""
    lib = [
        {"version": 7, "type": "context-options", "origin": "library", "browserName": "chromium"},
        {
            "type": "before",
            "callId": "call@39",
            "startTime": 10.0,
            "apiName": "page.goto",
            "class": "Frame",
            "method": "goto",
            "params": {"url": f"http://127.0.0.1:8765/checkout?session={SESSION}"},
        },
        {"type": "after", "callId": "call@39", "endTime": 20.0},
        {
            "type": "before",
            "callId": "call@40",
            "startTime": 21.0,
            "apiName": "locator.click",
            "class": "Frame",
            "method": "click",
            "params": {"selector": 'internal:testid=[data-testid="pay-now"s]'},
        },
        {
            "type": "after",
            "callId": "call@40",
            "endTime": 30.0,
            "error": {
                "message": "\x1b[31mTimeout 5000ms exceeded.\x1b[39m waiting for getByTestId('pay-now')"
            },
        },
        {
            "type": "console",
            "messageType": "error",
            "text": f"boom: token={CONSOLE_TOKEN}",
            "location": {"url": "http://127.0.0.1:8765/checkout", "lineNumber": 1, "columnNumber": 1},
            "pageId": PAGE,
        },
        {
            "type": "event",
            "class": "Page",
            "method": "pageError",
            "params": {"error": {"error": {"message": "TypeError: x is undefined"}}},
        },
        {"type": "frame-snapshot", "snapshot": {}},
        {"type": "screencast-frame", "pageId": PAGE, "sha1": f"{PAGE}-1.jpeg", "width": 1280, "height": 720},
    ]
    if not broken:
        lib = [e for e in lib if e.get("callId") != "call@40" and e["type"] not in {"console", "event"}]
    network = [
        {
            "type": "resource-snapshot",
            "snapshot": {
                "request": {
                    "method": "GET",
                    "url": f"http://127.0.0.1:8765/api/cart?token={QUERY_TOKEN}",
                    "headers": [
                        {"name": "Cookie", "value": f"sid={COOKIE}"},
                        {"name": "Authorization", "value": f"Bearer {BEARER}"},
                    ],
                },
                "response": {
                    "status": 500 if broken else 200,
                    "headers": [{"name": "Content-Type", "value": "application/json"}],
                },
            },
        }
    ]
    runner = [
        {
            "type": "before",
            "callId": "expect@13",
            "startTime": 31.0,
            "title": "console errors",
            "class": "Test",
            "method": "step",
            "params": {},
        },
        {
            "type": "after",
            "callId": "expect@13",
            "endTime": 32.0,
            **({"error": {"message": "console errors"}} if broken else {}),
        },
    ]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("0-trace.trace", "\n".join(json.dumps(e) for e in lib) + "\n")
        zf.writestr("0-trace.network", "\n".join(json.dumps(e) for e in network) + "\n")
        zf.writestr("test.trace", "\n".join(json.dumps(e) for e in runner) + "\n")
        zf.writestr(f"resources/{PAGE}-1.jpeg", b"\xff\xd8fakejpeg")
    return path


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "web/src/pages").mkdir(parents=True)
    (tmp_path / "web/src/Checkout.tsx").write_text(
        'export const Checkout = () => (\n  <button data-testid="pay-now" className="btn primary">Pay now</button>\n);\n'
    )
    (tmp_path / "web/src/pages/checkout.tsx").write_text("export default function Page() { return null; }\n")
    (tmp_path / "web/src/routes.ts").write_text(
        "export const routes = [\n  { path: '/checkout', element: 'Checkout' },\n];\n"
    )
    trace_zip(tmp_path / "trace.zip")
    return tmp_path


def make(root: Path, *, allow: bool = False) -> Server:
    return Server(
        "browser",
        browser.INSTRUCTIONS,
        list(browser.TOOLS),
        Context(root=root, server="browser", allow_actions=allow),
    )


LAB = {
    "name": "shop",
    "base_url": "http://127.0.0.1:3000",
    "pages": ["/", "/checkout"],
    "sensitive_selectors": ["#card-number"],
}


def test_lab_is_isolated_read_only_and_pinned(root: Path) -> None:
    out = make(root).call("browser_lab_create", LAB)
    lab = root / "browser-lab/shop"
    assert json.loads((lab / "package.json").read_text())["devDependencies"] == {
        "@playwright/test": browser.PLAYWRIGHT_VERSION
    }
    config = (lab / "playwright.config.ts").read_text()
    assert "trace: 'on'" in config and "workers: 1" in config and "retries: 0" in config
    spec = (lab / "tests/pages.spec.ts").read_text()
    assert 'page.locator("#card-number")' in spec and ".click(" not in spec and "favicon.ico" in spec
    assert out["plan"]["commands"][1] == "npx playwright install chromium"
    chrome = make(root).call("browser_lab_create", {**LAB, "name": "local", "channel": "chrome"})
    assert "channel: 'chrome'" in (root / "browser-lab/local/playwright.config.ts").read_text()
    assert "npx playwright install chromium" not in chrome["plan"]["commands"]


def test_lab_refuses_production_and_unapproved_runs(root: Path) -> None:
    with pytest.raises(ToolError, match="never production"):
        make(root).call("browser_lab_create", {**LAB, "base_url": "https://shop.example.com"})
    (root / ".dex").mkdir()
    (root / ".dex/browser.json").write_text(json.dumps({"test_hosts": ["staging.example.test"]}))
    make(root).call(
        "browser_lab_create", {**LAB, "name": "staging", "base_url": "https://staging.example.test"}
    )
    for bad in ({"pages": ["https://evil.example/"]}, {"sensitive_selectors": ["a`b"]}, {"name": "../x"}):
        with pytest.raises(ToolError):
            make(root).call("browser_lab_create", {**LAB, **bad})
    created = make(root).call("browser_lab_create", LAB)
    with pytest.raises(ToolError, match="actions are off"):
        make(root).call("browser_lab_run", {**LAB, "approval": created["approval"]})
    with pytest.raises(ToolError, match="doesn't match"):
        make(root, allow=True).call(
            "browser_lab_run", {**LAB, "pages": ["/"], "approval": created["approval"]}
        )
    (root / "browser-lab/shop/tests/pages.spec.ts").write_text("// edited")
    with pytest.raises(ToolError, match="exists and differs"):
        make(root).call("browser_lab_create", LAB)


def test_trace_is_read(root: Path) -> None:
    out = make(root).call("browser_trace", {"trace": "trace.zip"})
    assert out["status"] == "failed" and out["summary"]["format_version"] == 7
    failed = {a["api"]: a for a in out["failed_actions"]}
    assert failed["locator.click"]["selector"] == 'internal:testid=[data-testid="pay-now"s]'
    assert failed["locator.click"]["error"].startswith("Timeout 5000ms exceeded.")  # colour codes removed
    assert "console errors" in failed
    assert out["page_errors"] == ["TypeError: x is undefined"]
    assert out["failed_requests"][0]["status"] == 500 and QUERY_TOKEN not in out["failed_requests"][0]["url"]
    assert out["summary"]["screenshots"] == 1 and out["summary"]["dom_snapshots"] == 1
    trace_zip(root / "ok.zip", broken=False)
    assert make(root).call("browser_trace", {"trace": "ok.zip"})["status"] == "ok"


def test_unsafe_archives_are_refused(root: Path) -> None:
    with zipfile.ZipFile(root / "bomb.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("0-trace.trace", "x" * 5_000_000)
    with zipfile.ZipFile(root / "escape.zip", "w") as zf:
        zf.writestr("../0-trace.trace", "{}")
    with zipfile.ZipFile(root / "other.zip", "w") as zf:
        zf.writestr("readme.txt", "hi")
    (root / "plain.zip").write_text("not a zip")
    for name, msg in (
        ("bomb.zip", "zip bomb"),
        ("escape.zip", "outside the archive"),
        ("other.zip", "no .trace"),
        ("plain.zip", "not a zip"),
    ):
        with pytest.raises(ToolError, match=msg):
            make(root).call("browser_trace", {"trace": name})


def test_selectors_and_pages_map_to_source(root: Path) -> None:
    out = make(root).call("browser_map", {"trace": "trace.zip", "paths": ["web"]})
    sel = {s["selector"]: s for s in out["selectors"]}
    hit = sel['internal:testid=[data-testid="pay-now"s]']["matches"][0]
    assert (hit["file"], hit["line"], hit["kind"]) == ("web/src/Checkout.tsx", 2, "testid")
    route = out["routes"][0]
    assert SESSION not in route["url"]
    kinds = {(m["file"], m["kind"]) for m in route["matches"]}
    assert ("web/src/routes.ts", "route") in kinds and ("web/src/pages/checkout.tsx", "file-route") in kinds
    gone = make(root).call("browser_map", {"selectors": ["#renamed-button"], "paths": ["web"]})
    assert gone["findings"][0]["rule"] == "browser.selector-unmapped"
    assert browser.selector_targets('internal:role=button[name="Pay now"i]') == [
        ("role", "button"),
        ("text", "Pay now"),
    ]
    with pytest.raises(ToolError, match="nothing to map"):
        make(root).call("browser_map", {})


def test_evidence_is_redacted(root: Path) -> None:
    out = make(root).call("browser_evidence", {"trace": "trace.zip", "run_id": "run-7"})
    bundle_path = root / out["artifacts"][0]["path"]
    text = bundle_path.read_text()
    for secret in (CONSOLE_TOKEN, QUERY_TOKEN, COOKIE, BEARER, SESSION):
        assert secret not in text
    bundle = json.loads(text)
    assert bundle["run_id"] == "run-7" and bundle["screenshots"]["copied"] == []
    rules = sorted({f["rule"] for f in out["findings"]})
    assert rules == [
        "browser.action-failed",
        "browser.console",
        "browser.page-error",
        "browser.request-failed",
    ]
    assert any(a["media_type"] == "application/sarif+json" for a in out["artifacts"])
    with_shots = make(root).call("browser_evidence", {"trace": "trace.zip", "include_screenshots": True})
    shots = [a for a in with_shots["artifacts"] if a["media_type"] == "image/jpeg"]
    assert len(shots) == 1 and shots[0]["sensitivity"] == "confidential" and with_shots["warnings"]
