"""What every Dex MCP server shares: the result envelope, evidence, approval, redaction and a careful HTTP client.

The rules the servers follow, so they hold everywhere:

* **Read first, act only when asked twice.** A tool that changes something outside this machine (starts a build,
  imports a dashboard, opens a pull request) is off unless the server was started with ``--allow-actions``. Even
  then it needs the ``approval`` digest of the exact plan its ``preview`` tool showed. Change one parameter and the
  digest no longer matches, so what runs is what a person saw.
* **Credentials come from the environment only**, never from arguments, configuration files or results. Everything
  a tool returns or writes passes through :func:`redact`.
* **Evidence, not claims.** Results use one envelope: ``status``, ``artifacts`` (path, media type, sha256,
  sensitivity, producer and schema version), ``findings``, ``provenance`` and ``warnings``. Findings are also
  written as SARIF under ``dex-evidence/``, where ``ananke triage findings`` picks them up.
* **Stable output.** :func:`stable_digest` hashes canonical JSON with timestamps left out, so the same input gives
  the same digest on every run.
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dex_trove import __version__

RESULT_SCHEMA = "dex-trove/mcp-result@1"
EVIDENCE_DIR = "dex-evidence"
STATE_DIR = ".dex/mcp"
TIMESTAMP_KEYS = frozenset(
    {
        "generated_at",
        "triggered_at",
        "recorded_at",
        "checked_at",
        "started_at",
        "finished_at",
        "at",
        "duration_ms",
    }
)
MAX_RESPONSE_BYTES = 20 * 1024 * 1024
SEVERITIES = ("error", "warning", "note")


class ToolError(Exception):
    """A failure the caller can act on: the message says what's wrong and what to do about it."""


@dataclass
class Context:
    """Where a server may read and write, and whether it may act."""

    root: Path
    server: str
    allow_actions: bool = False
    env: Mapping[str, str] = field(default_factory=lambda: os.environ)
    evidence_dir: Path | None = None
    sleep: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        self.root = self.root.resolve()
        if not self.root.is_dir():
            raise ToolError(f"{self.root} is not a folder: pass --root with the project the server works on")

    @property
    def state(self) -> Path:
        """Ledgers and indexes: ``.dex/mcp/<server>/``, which analysers skip."""
        return self.root / STATE_DIR / self.server

    @property
    def evidence(self) -> Path:
        """Evidence another tool should read: ``dex-evidence/<server>/`` unless ``--evidence`` says otherwise."""
        return (self.evidence_dir or self.root / EVIDENCE_DIR) / self.server

    def path(self, value: str, *, must_exist: bool = True) -> Path:
        """A path inside the project root, or a :class:`ToolError`. Symlinks are resolved before the check."""
        if not isinstance(value, str) or not value or "\x00" in value:
            raise ToolError("a path is required")
        candidate = (self.root / value).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ToolError(f"{value}: outside the project root {self.root}; the server only reads inside it")
        if must_exist and not candidate.exists():
            raise ToolError(f"{value}: not found under {self.root}")
        return candidate

    def config(self, name: str) -> dict[str, Any]:
        """``.dex/<name>.json`` from the project, or an empty dict."""
        path = self.root / ".dex" / f"{name}.json"
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ToolError(f".dex/{name}.json: not valid JSON ({exc})") from exc
        if not isinstance(data, dict):
            raise ToolError(f".dex/{name}.json: expected an object")
        return data

    def audit(self, event: str, **details: Any) -> None:
        """Appends one line to ``.dex/mcp/audit.jsonl``: every action, approved or refused."""
        log = self.root / STATE_DIR / "audit.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        line = {"at": now_iso(), "server": self.server, "event": event, **details}
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(redact_obj(line), sort_keys=True) + "\n")


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ── Digests and approval ────────────────────────────────────────────────────


def _strip_times(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_times(v) for k, v in value.items() if k not in TIMESTAMP_KEYS}
    if isinstance(value, list):
        return [_strip_times(v) for v in value]
    return value


def canonical(value: Any) -> str:
    return json.dumps(_strip_times(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_digest(value: Any) -> str:
    """sha256 of canonical JSON with timestamps removed: equal inputs, equal digests."""
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def approval_for(plan: Mapping[str, Any]) -> str:
    return "sha256:" + stable_digest(plan)


def require_approval(ctx: Context, plan: Mapping[str, Any], given: object, *, action: str) -> None:
    """Refuses unless actions are on and ``given`` is the digest of exactly this plan. Both outcomes are audited."""
    if not ctx.allow_actions:
        ctx.audit("refused", action=action, reason="actions off")
        raise ToolError(
            f"{action} changes something outside this machine, and actions are off. Nothing was done. To allow it, "
            "restart the server with --allow-actions, run the preview again and pass its approval digest."
        )
    expected = approval_for(plan)
    if given != expected:
        ctx.audit("refused", action=action, reason="approval mismatch")
        raise ToolError(
            "approval doesn't match this plan, so nothing was done. Something changed since the preview (or no "
            "approval was given): run the preview again, check it, and pass the approval digest it returns."
        )
    ctx.audit("approved", action=action, approval=expected)


# ── Redaction ───────────────────────────────────────────────────────────────

_SECRET_PATTERNS = [
    (re.compile(r"(?i)\b(authorization|proxy-authorization)\s*[:=]\s*\S+(\s+\S+)?"), r"\1: [REDACTED]"),
    (re.compile(r"(?i)\b(bearer|basic|token)\s+[A-Za-z0-9._~+/=-]{8,}"), r"\1 [REDACTED]"),
    (
        re.compile(
            r"(?i)([?&;\s\"']|^)((?:access_|api_|auth_|refresh_|id_|client_)?(?:token|key|secret|password|passwd|pwd|"
            r"session|sig|signature|apikey|api-key))=([^&\s\"';]+)"
        ),
        r"\1\2=[REDACTED]",
    ),
    (
        re.compile(
            r"(?i)\"(password|passwd|secret|token|api_?key|apikey|authorization|cookie)\"\s*:\s*\"[^\"]*\""
        ),
        r'"\1": "[REDACTED]"',
    ),
    (re.compile(r"(https?://)[^/\s:@]+:[^/\s@]+@"), r"\1[REDACTED]@"),
    (re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"), "[REDACTED]"),
    (re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b"), "[REDACTED]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "[REDACTED]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), "[REDACTED]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED]"),
]
SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x-auth-token",
        "jenkins-crumb",
    }
)


def redact(text: str) -> str:
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_obj(value: Any) -> Any:
    """Redacts strings anywhere in a JSON-like value, and the values of sensitive header or key names."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_obj(v) for v in value]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and key.lower() in SENSITIVE_HEADERS and item not in (None, ""):
                out[key] = "[REDACTED]"
            else:
                out[key] = redact_obj(item)
        return out
    return value


# ── Results and evidence ────────────────────────────────────────────────────


def finding(
    severity: str,
    message: str,
    *,
    rule: str,
    uri: str = "",
    line: int | None = None,
    status: str = "observed",
    remediation: str = "",
) -> dict[str, Any]:
    if severity not in SEVERITIES:
        raise ValueError(severity)
    item: dict[str, Any] = {"severity": severity, "rule": rule, "message": message, "status": status}
    if uri:
        item["uri"] = uri
    if line:
        item["line"] = line
    if remediation:
        item["remediation"] = remediation
    return item


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def artifact(
    ctx: Context, path: Path, media_type: str, *, schema: str = "", sensitivity: str = "internal"
) -> dict[str, Any]:
    try:
        shown = path.relative_to(ctx.root).as_posix()
    except ValueError:
        shown = path.as_posix()
    return {
        "path": shown,
        "media_type": media_type,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "sensitivity": sensitivity,
        "producer": f"dex-trove/{ctx.server}@{__version__}",
        "schema": schema or RESULT_SCHEMA,
    }


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(redact_obj(data), indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(redact(text), encoding="utf-8")
    return path


def result(
    ctx: Context,
    status: str,
    *,
    artifacts: list[dict[str, Any]] | None = None,
    findings: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    inputs: Mapping[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """The common envelope. ``digest`` covers everything but timestamps, so reruns compare equal."""
    body: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "status": status,
        **extra,
        "artifacts": artifacts or [],
        "findings": findings or [],
        "warnings": warnings or [],
        "provenance": [
            {
                "producer": f"dex-trove/{ctx.server}",
                "version": __version__,
                "inputs_digest": stable_digest(inputs or {}),
                "generated_at": now_iso(),
            }
        ],
    }
    body = redact_obj(body)
    body["digest"] = stable_digest({k: v for k, v in body.items() if k != "provenance"})
    return body


def write_sarif(ctx: Context, name: str, findings: list[dict[str, Any]], *, tool: str) -> Path:
    """Findings as SARIF 2.1.0 under ``dex-evidence/<server>/``, where ``ananke triage findings`` reads them."""
    rules = sorted({f["rule"] for f in findings})
    results = []
    for f in findings:
        entry: dict[str, Any] = {
            "ruleId": f["rule"],
            "level": f["severity"],
            "message": {"text": f["message"] + (f" Fix: {f['remediation']}" if f.get("remediation") else "")},
            "properties": {"status": f.get("status", "observed")},
        }
        if f.get("uri"):
            region = {"startLine": f["line"]} if f.get("line") else {}
            entry["locations"] = [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": f["uri"]},
                        **({"region": region} if region else {}),
                    }
                }
            ]
        results.append(entry)
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": tool,
                        "version": __version__,
                        "informationUri": "https://neo-pragnya.github.io/Dex-Trove/",
                        "rules": [{"id": r} for r in rules],
                    }
                },
                "results": results,
            }
        ],
    }
    return write_json(ctx.evidence / f"{name}.sarif", sarif)


# ── HTTP ────────────────────────────────────────────────────────────────────


def is_loopback(host: str) -> bool:
    if host in {"localhost", "localhost."}:
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def check_url(url: str, *, what: str) -> urllib.parse.SplitResult:
    """https anywhere, plain http only on this machine (a local test instance)."""
    parts = urllib.parse.urlsplit(url or "")
    if parts.scheme not in {"https", "http"} or not parts.hostname:
        raise ToolError(f"{what}: {url!r} isn't an http(s) URL")
    if parts.username or parts.password:
        raise ToolError(f"{what}: put credentials in the environment, not in the URL")
    if parts.scheme == "http" and not is_loopback(parts.hostname):
        raise ToolError(
            f"{what}: plain http is only allowed for a local test instance; use https for {parts.hostname}"
        )
    return parts


class _SameHostRedirects(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to the same scheme and host, so credentials never travel elsewhere."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        old, new = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
        if (old.scheme, old.netloc) != (new.scheme, new.netloc):
            raise ToolError(f"refused a redirect from {old.netloc} to {new.netloc}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_SameHostRedirects)


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ToolError(f"expected JSON from the server, got {self.body[:80]!r}") from exc


def basic_auth(user: str, token: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{token}".encode()).decode("ascii")


def http(
    ctx: Context,
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = 30.0,
    retries: int = 2,
    service: str,
    auth_hint: str = "",
) -> Response:
    """One request with bounded retries (connection errors and 502/503/504 only, never for POST twice on 5xx).

    401 and 403 become an actionable :class:`ToolError`; other statuses are returned for the caller to judge.
    """
    check_url(url, what=service)
    attempts = max(1, min(retries + 1, 5))
    last: Exception | None = None
    for attempt in range(attempts):
        req = urllib.request.Request(url, data=body, method=method, headers=dict(headers or {}))  # noqa: S310 - scheme checked
        try:
            with _OPENER.open(req, timeout=timeout) as resp:
                data = resp.read(MAX_RESPONSE_BYTES + 1)
                if len(data) > MAX_RESPONSE_BYTES:
                    raise ToolError(f"{service}: response larger than {MAX_RESPONSE_BYTES} bytes, refused")
                return Response(resp.status, {k.lower(): v for k, v in resp.headers.items()}, data)
        except urllib.error.HTTPError as exc:
            data = exc.read(64 * 1024) if exc.fp else b""
            if exc.code in (401, 403):
                raise ToolError(
                    f"{service} refused the request ({exc.code} {'unauthenticated' if exc.code == 401 else 'forbidden'})."
                    + (f" {auth_hint}" if auth_hint else "")
                ) from exc
            if exc.code in (502, 503, 504) and method == "GET" and attempt + 1 < attempts:
                last = exc
                ctx.sleep(min(2.0**attempt, 10.0))
                continue
            return Response(exc.code, {k.lower(): v for k, v in (exc.headers or {}).items()}, data)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
            if attempt + 1 < attempts and method == "GET":
                ctx.sleep(min(2.0**attempt, 10.0))
                continue
            break
    reason = getattr(last, "reason", last)
    raise ToolError(f"{service} at {urllib.parse.urlsplit(url).netloc} couldn't be reached: {reason}")
