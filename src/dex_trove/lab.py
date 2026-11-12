"""Skill safety and effectiveness lab (ADV15): what an item can do, what it costs, whether it's found, and what
changed since the last copy, before it's published.

* **Permissions**, read from every file with its line: network access, starting processes or evaluating code,
  writing or deleting files, reading the environment or secrets, privilege escalation, piping a download into a
  shell, and hooks or MCP servers it would register. Nothing in the item runs.
* **Token cost:** what's always loaded (the description), what loads when it's activated (the entry file) and
  everything it ships, estimated at four characters per token.
* **Effectiveness:** with cases (``[{"prompt": ..., "expect": true}]``), whether Dex's own search ranks the item in
  the top three for prompts that should find it, and keeps it out for prompts that shouldn't. Without cases this is
  *unknown*, never assumed.
* **Regressions:** with an older copy (``--against DIR``), permissions it gained and how much its cost grew.

The **verdict** is *block* (a script that pipes a download into a shell, or credentials embedded), *review* (it can
reach the network, start processes, write files, read secrets, its documentation tells the reader to pipe an installer
into a shell, it gained a permission, or it's found for under 80% of its cases) or *publishable*.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "dex/lab@1"
TEXT_SUFFIXES = {
    ".md", ".py", ".sh", ".js", ".mjs", ".ts", ".json", ".yaml", ".yml", ".toml", ".ps1", ".txt", ".bash",
}  # fmt: skip
MAX_FILE_BYTES = 2_000_000
TOP_K = 3
_DOC_SUFFIXES = {".md", ".txt"}
_REMOTE_EXEC = (
    r"\b(curl|wget|iwr|Invoke-WebRequest)\b[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b|iex\s*\(\s*(iwr|irm|New-Object)"
)
_CREDENTIAL = r"\b(AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|sk_live_[A-Za-z0-9]{16,}|xox[bp]-[A-Za-z0-9-]{20,})\b"
_NETWORK = (
    r"\b(requests\.(get|post|put|delete|patch)|urllib\.request|http\.client|httpx\.|aiohttp\.|fetch\(|"
    r"axios\.|curl\s|wget\s|Invoke-WebRequest)"
)
_PROCESS = r"\b(subprocess\.|os\.system\(|os\.popen\(|child_process|execSync\(|spawn\(|Popen\(|eval\(|exec\()"
_WRITES = (
    r"\b(write_text\(|write_bytes\(|shutil\.rmtree\(|os\.remove\(|unlink\(|fs\.writeFile|rm\s+-rf\s)"
    r"|open\([^)]*['\"][wa]b?['\"]"
)
_SECRETS = r"\b(os\.environ|os\.getenv\(|process\.env|keyring\.|getpass\(|\.aws/credentials|id_rsa)\b"
_PRIVILEGE = r"(^|[\s;&|`(])sudo\s|\bchmod\s+(\+s|[0-7]?7[0-7][0-7])\b|\bsetuid\b"
_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("remote-exec", "block", re.compile(_REMOTE_EXEC, re.I)),
    ("embedded-credential", "block", re.compile(_CREDENTIAL)),
    ("privilege", "review", re.compile(_PRIVILEGE)),
    ("network", "review", re.compile(_NETWORK)),
    ("process", "review", re.compile(_PROCESS)),
    ("writes-files", "review", re.compile(_WRITES)),
    ("reads-secrets", "review", re.compile(_SECRETS)),
)


def _tokens(text: str) -> int:
    return (len(text) + 3) // 4


def _files(folder: Path) -> list[Path]:
    if folder.is_file():
        return [folder]
    return sorted(p for p in folder.rglob("*") if p.is_file())


def permissions(folder: Path) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    base = folder if folder.is_dir() else folder.parent
    for path in _files(folder):
        rel = path.relative_to(base).as_posix()
        if path.name in {".mcp.json", "hooks.json"}:
            kind = "registers-mcp-server" if path.name == ".mcp.json" else "registers-hooks"
            found.append({"permission": kind, "level": "review", "evidence": rel})
        if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > MAX_FILE_BYTES:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for no, line in enumerate(lines, start=1):
            for name, level, pattern in _RULES:
                if pattern.search(line):
                    if name == "remote-exec" and path.suffix.lower() in _DOC_SUFFIXES:
                        # documentation telling someone to pipe an installer into a shell: an agent following the
                        # item might run it, so it's reviewed; a script that does it is blocked
                        name, level = "instructs-remote-exec", "review"
                    found.append(
                        {
                            "permission": name,
                            "level": level,
                            "evidence": f"{rel}:{no}",
                            "text": line.strip()[:160],
                        }
                    )
    return found


def _summary(found: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for f in found:
        out[f["permission"]] = out.get(f["permission"], 0) + 1
    return dict(sorted(out.items()))


def cost(item: dict[str, Any], folder: Path) -> dict[str, int]:
    entry = folder / item["entry"] if folder.is_dir() and item.get("entry") else folder
    texts = [
        p for p in _files(folder) if p.suffix.lower() in TEXT_SUFFIXES and p.stat().st_size <= MAX_FILE_BYTES
    ]
    total = sum(_tokens(p.read_text(encoding="utf-8", errors="replace")) for p in texts)
    active = _tokens(entry.read_text(encoding="utf-8", errors="replace")) if entry.is_file() else 0
    return {
        "always_loaded": _tokens(str(item.get("description") or "")),
        "on_activation": active,
        "everything": total,
    }


def effectiveness(
    item: dict[str, Any], items: list[dict[str, Any]], cases: list[dict[str, Any]]
) -> dict[str, Any]:
    from dex_trove import semantic

    key = f"{item['kind']}:{item['id']}"
    rows = []
    for case in cases:
        ranked = [f"{it['kind']}:{it['id']}" for it in semantic.rank(items, str(case["prompt"]))[:TOP_K]]
        found = key in ranked
        want = bool(case.get("expect", True))
        rows.append(
            {
                "prompt": case["prompt"],
                "expect": want,
                "found_in_top": found,
                "ok": found == want,
                "top": ranked,
            }
        )
    should = [r for r in rows if r["expect"]]
    should_not = [r for r in rows if not r["expect"]]
    return {
        "cases": len(rows),
        "recall": round(sum(r["found_in_top"] for r in should) / len(should), 3) if should else None,
        "false_triggers": sum(r["found_in_top"] for r in should_not),
        "accuracy": round(sum(r["ok"] for r in rows) / len(rows), 3) if rows else None,
        "rows": rows,
        "status": "measured" if rows else "unknown: no cases given",
    }


def load_cases(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{path}: {exc}") from exc
    if not isinstance(data, list) or not all(isinstance(c, dict) and c.get("prompt") for c in data):
        raise ValueError(f'{path.name} isn\'t a JSON list of {{"prompt": ..., "expect": true|false}}')
    return data


def assess(
    item: dict[str, Any],
    items: list[dict[str, Any]],
    folder: Path,
    *,
    cases: list[dict[str, Any]] | None = None,
    against: Path | None = None,
) -> dict[str, Any]:
    found = permissions(folder)
    spend = cost(item, folder)
    eff = effectiveness(item, items, cases or [])
    regression = None
    if against is not None:
        if not against.exists():
            raise ValueError(f"{against} doesn't exist")
        before = _summary(permissions(against))
        old_cost = cost(item, against)
        now = _summary(found)
        regression = {
            "gained": sorted(set(now) - set(before)),
            "lost": sorted(set(before) - set(now)),
            "cost_change": {k: spend[k] - old_cost.get(k, 0) for k in spend},
        }
    reasons = []
    blocks = sorted({f["permission"] for f in found if f["level"] == "block"})
    for b in blocks:
        reasons.append(f"{b}: {next(f['evidence'] for f in found if f['permission'] == b)}")
    reviews = sorted({f["permission"] for f in found if f["level"] == "review"})
    if reviews:
        reasons.append("can " + ", ".join(reviews))
    if regression and regression["gained"]:
        reasons.append("gained " + ", ".join(regression["gained"]) + " since the older copy")
    if eff["recall"] is not None and eff["recall"] < 0.8:
        reasons.append(f"found for only {eff['recall']:.0%} of the prompts that should find it")
    if eff["false_triggers"]:
        reasons.append(f"found for {eff['false_triggers']} prompts that shouldn't find it")
    verdict = "block" if blocks else "review" if reasons else "publishable"
    return {
        "schema": SCHEMA,
        "item": f"{item['kind']}:{item['id']}",
        "executes_code": bool(item.get("executes_code")),
        "verdict": verdict,
        "reasons": reasons,
        "permissions": _summary(found),
        "evidence": found[:200],
        "tokens": spend,
        "effectiveness": eff,
        "regression": regression,
    }


def survey(items: list[dict[str, Any]], trove: Path) -> dict[str, Any]:
    """Every item's permissions and cost, without effectiveness cases: a governance overview."""
    from dex_trove import catalog

    rows = []
    for it in items:
        folder = catalog.item_path(it, trove)
        if not folder.exists():
            continue
        r = assess(it, items, folder)
        rows.append(
            {
                "item": r["item"],
                "verdict": r["verdict"],
                "permissions": r["permissions"],
                "tokens": r["tokens"],
                "reasons": r["reasons"],
            }
        )
    verdicts: dict[str, int] = {}
    perms: dict[str, int] = {}
    for row in rows:
        verdicts[row["verdict"]] = verdicts.get(row["verdict"], 0) + 1
        for p in row["permissions"]:
            perms[p] = perms.get(p, 0) + 1
    costs = sorted(row["tokens"]["always_loaded"] for row in rows)
    return {
        "schema": "dex/lab-survey@1",
        "items": len(rows),
        "verdicts": dict(sorted(verdicts.items())),
        "items_with_permission": dict(sorted(perms.items())),
        "always_loaded_tokens": {
            "median": costs[len(costs) // 2] if costs else 0,
            "max": costs[-1] if costs else 0,
        },
        "blocked": [row for row in rows if row["verdict"] == "block"],
        "rows": rows,
    }


def to_markdown(r: dict[str, Any]) -> str:
    t = r["tokens"]
    e = r["effectiveness"]
    measured = (
        f"; recall {e['recall']}, false triggers {e['false_triggers']}, accuracy {e['accuracy']}"
        if e["cases"]
        else ""
    )
    lines = [
        f"# {r['item']}: {r['verdict']}",
        "",
        *(f"- {x}" for x in r["reasons"] or ["nothing found that needs review"]),
        "",
        f"Tokens: {t['always_loaded']} always loaded, {t['on_activation']} on activation, {t['everything']} in all.",
        "",
        f"Effectiveness: {e['status']}{measured}",
        "",
    ]
    if r["evidence"]:
        lines += ["| Permission | Where | Line |", "| --- | --- | --- |"]
        lines += [
            f"| {f['permission']} | `{f['evidence']}` | `{f.get('text', '')}` |" for f in r["evidence"][:40]
        ]
        lines.append("")
    if r["regression"]:
        g = r["regression"]
        lines += [
            f"Since the older copy: gained {', '.join(g['gained']) or 'nothing'}; "
            f"lost {', '.join(g['lost']) or 'nothing'}; cost change {g['cost_change']}.",
            "",
        ]
    return "\n".join(lines)
