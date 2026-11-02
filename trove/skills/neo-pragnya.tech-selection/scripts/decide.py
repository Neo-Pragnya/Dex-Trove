#!/usr/bin/env python3
"""Technology decision records from evidence: alternatives, trade-offs, licence and policy checks.

  decide.py check request.json            # validate evidence, citations, licences and exceptions
  decide.py record request.json -o TDR.md # write the decision record (refuses when a check fails)

request.json (schema "tech-selection/request@1"):
  question, context, chosen (an option name or null while undecided), decided_by
  constraints: {licences_allowed: [...], platforms: [...], max_cost: "low|medium|high", other: [...]}
  options: [{name, licence, platforms: [...], cost, evidence: [{claim, kind, cite}], pros: [...], cons: [...]}]
      evidence kind: benchmark | doc | experience | security | popularity
      cite: an https URL, or a local file path optionally with #anchor (resolved relative to the request file)
  enterprise_docs: [{title, cite}]   approved architecture documents the choice must respect
  exceptions: [{policy, reason, owner, expires}]   needed when the chosen option breaks a constraint

Checks: a choice backed only by popularity is refused; every citation must resolve (local files must exist and
anchors must match a heading; URLs must be https); a licence outside licences_allowed is flagged; a chosen option
that breaks a constraint needs an exception with a named owner. Output is deterministic. Python 3.9+, stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA = "tech-selection/request@1"
COST = {"low": 0, "medium": 1, "high": 2}


class RequestError(Exception):
    pass


def load(path: Path) -> dict:
    if not path.is_file():
        raise RequestError(f"no request at {path}; start from references/request.example.json")
    try:
        req = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise RequestError(f"{path} is not valid JSON: {exc}") from exc
    if req.get("schema") != SCHEMA:
        raise RequestError(f"{path}: schema must be {SCHEMA!r}")
    for key in ("question", "options"):
        if not req.get(key):
            raise RequestError(f"{path}: {key!r} is required")
    return req


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9 -]", "", text.lower()).strip().replace(" ", "-")


def resolve(cite: str, base: Path) -> str | None:
    """None when the citation resolves, otherwise why it doesn't."""
    if not cite:
        return "empty citation"
    if re.match(r"^[a-z]+://", cite):
        return None if cite.startswith("https://") else f"{cite}: only https links are accepted"
    path, _, anchor = cite.partition("#")
    f = (base / path).resolve()
    if not f.is_file():
        return f"{cite}: file not found"
    if anchor:
        heads = {_slug(m.group(1)) for m in re.finditer(r"^#+\s+(.+?)\s*$", f.read_text(encoding="utf-8"), re.M)}
        if anchor not in heads:
            return f"{cite}: no heading #{anchor}"
    return None


def check(req: dict, base: Path) -> tuple[list[str], list[str]]:
    """(problems that block a record, flags to show in it)."""
    problems: list[str] = []
    flags: list[str] = []
    c = req.get("constraints", {})
    allowed = set(c.get("licences_allowed", []))
    platforms = set(c.get("platforms", []))
    names = [o["name"] for o in req["options"]]
    if len(names) < 2:
        problems.append("compare at least two options; a record with one option isn't a decision")
    for o in req["options"]:
        ev = o.get("evidence", [])
        if not ev:
            problems.append(f"{o['name']}: no evidence")
        for e in ev:
            why = resolve(e.get("cite", ""), base)
            if why:
                problems.append(f"{o['name']}: citation doesn't resolve ({why})")
        if allowed and o.get("licence") not in allowed:
            flags.append(f"{o['name']}: licence {o.get('licence') or 'unknown'} is not in the allowed list")
        if platforms and not platforms <= set(o.get("platforms", [])):
            flags.append(f"{o['name']}: doesn't cover platforms {', '.join(sorted(platforms - set(o.get('platforms', []))))}")
        if c.get("max_cost") and COST.get(o.get("cost", ""), 3) > COST[c["max_cost"]]:
            flags.append(f"{o['name']}: cost {o.get('cost', 'unknown')} exceeds {c['max_cost']}")
    for d in req.get("enterprise_docs", []):
        why = resolve(d.get("cite", ""), base)
        if why:
            problems.append(f"enterprise document {d.get('title')!r}: {why}")
    chosen = req.get("chosen")
    if chosen:
        if chosen not in names:
            problems.append(f"chosen option {chosen!r} isn't one of the options")
        else:
            opt = next(o for o in req["options"] if o["name"] == chosen)
            kinds = {e.get("kind") for e in opt.get("evidence", [])}
            if kinds <= {"popularity"}:
                problems.append(f"{chosen}: chosen on popularity alone; add benchmark, doc, security or experience evidence")
            broken = [f for f in flags if f.startswith(chosen + ":")]
            covered = {x.get("policy") for x in req.get("exceptions", []) if x.get("owner")}
            for f in broken:
                policy = "licence" if "licence" in f else "platforms" if "platforms" in f else "cost"
                if policy not in covered:
                    problems.append(f"{f}; add an exception for {policy!r} with a named owner, or choose another option")
            if not req.get("decided_by"):
                problems.append("a chosen option needs decided_by")
    for x in req.get("exceptions", []):
        if not x.get("owner"):
            problems.append(f"exception for {x.get('policy')!r} has no owner")
    return problems, flags


def render(req: dict, flags: list[str]) -> str:
    chosen = req.get("chosen")
    status = f"Decided: **{chosen}** (by {req['decided_by']})" if chosen else "**Proposed**: no option chosen yet"
    lines = [f"# Technology decision: {req['question']}", "", status, "", "## Context", "", req.get("context", "").strip() or "—", ""]
    c = req.get("constraints", {})
    lines += ["## Constraints", ""]
    for k in ("licences_allowed", "platforms"):
        if c.get(k):
            lines.append(f"- {k.replace('_', ' ')}: {', '.join(c[k])}")
    if c.get("max_cost"):
        lines.append(f"- maximum cost: {c['max_cost']}")
    lines += [f"- {o}" for o in c.get("other", [])]
    lines += ["", "## Options", "", "| Option | Licence | Platforms | Cost | Evidence |", "| --- | --- | --- | --- | --- |"]
    for o in req["options"]:
        ev = "; ".join(f"{e.get('kind')}: {e.get('claim')} ([source]({e.get('cite')}))" for e in o.get("evidence", []))
        lines.append(f"| {o['name']} | {o.get('licence', '?')} | {', '.join(o.get('platforms', []))} | {o.get('cost', '?')} | {ev} |")
    lines += ["", "## Trade-offs", ""]
    for o in req["options"]:
        lines.append(f"**{o['name']}**: + " + ("; ".join(o.get("pros", [])) or "—") + " · − " + ("; ".join(o.get("cons", [])) or "—"))
        lines.append("")
    if req.get("enterprise_docs"):
        lines += ["## Enterprise architecture", ""] + [f"- [{d['title']}]({d['cite']})" for d in req["enterprise_docs"]] + [""]
    lines += ["## Flags", ""] + ([f"- {f}" for f in flags] or ["- none"]) + [""]
    lines += ["## Policy exceptions", ""]
    lines += [f"- **{x['policy']}**: {x.get('reason', '')} — owner {x['owner']}" + (f", expires {x['expires']}" if x.get("expires") else "")
              for x in req.get("exceptions", [])] or ["- none"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("check", "record"):
        x = sub.add_parser(name)
        x.add_argument("request", type=Path)
        if name == "record":
            x.add_argument("-o", "--output")
    a = p.parse_args(argv)
    try:
        req = load(a.request)
        problems, flags = check(req, a.request.resolve().parent)
    except RequestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for f in flags:
        print(f"flag: {f}")
    for pr in problems:
        print(f"✗ {pr}", file=sys.stderr)
    if problems:
        return 1
    if a.cmd == "check":
        print(f"✓ {len(req['options'])} options checked")
        return 0
    text = render(req, flags)
    if a.output:
        Path(a.output).write_text(text, encoding="utf-8")
        print(f"wrote {a.output}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
