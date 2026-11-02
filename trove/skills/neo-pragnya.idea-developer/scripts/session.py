#!/usr/bin/env python3
"""Idea developer session: a scoped interview that becomes a living PRD and an Ananke spec handoff.

Everything lives in one JSON file (default idea-session.json), so a session can stop and resume anywhere:

  session.py init --title "Team expense app" --domain web-app
  session.py next                       # the next unanswered questions, most important first
  session.py answer goal-1 "Let staff file expenses from a phone in under a minute"
  session.py assume "Single currency for v1" --risk "multi-currency teams can't adopt it"
  session.py decide "Mobile-first web app, no native apps in v1" --from goal-1,users-1 --kind scope
  session.py option "Web stack" --name "Next.js + Postgres" --evidence "team knows React" --cost low
  session.py approve D1 --by "Product owner"
  session.py prd -o PRD.md              # actors, outcomes, out of scope, decisions, open questions
  session.py handoff                    # refuses while anything is unapproved; prints `ananke spec create …`

Rules it enforces: a decision must cite the answers it comes from; nothing unapproved is shown as approved; output
is deterministic (sorted, no timestamps in the rendered PRD). Python 3.9+, standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUESTIONS = HERE.parent / "references" / "questions.json"
SCHEMA = "idea-developer/session@1"


class SessionError(Exception):
    pass


def load(path: Path) -> dict:
    if not path.is_file():
        raise SessionError(f"no session at {path}: start one with `session.py init --title … --domain …`")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise SessionError(f"{path} is not valid JSON ({exc}); restore it from version control") from exc
    if data.get("schema") != SCHEMA:
        raise SessionError(f"{path} is not an idea-developer session (schema {data.get('schema')!r})")
    return data


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def bank() -> dict:
    return json.loads(QUESTIONS.read_text(encoding="utf-8"))


def cmd_init(a: argparse.Namespace) -> None:
    b = bank()
    domains = sorted(b["domains"])
    if a.domain not in b["domains"]:
        raise SessionError(f"unknown domain {a.domain!r}; choose from: {', '.join(domains)}")
    if a.file.exists() and not a.force:
        raise SessionError(f"{a.file} exists; resume it, or pass --force to start over")
    questions = [q for q in b["core"] + b["domains"][a.domain]]
    save(a.file, {"schema": SCHEMA, "title": a.title, "domain": a.domain, "questions": questions, "answers": {},
                  "assumptions": [], "decisions": [], "options": [], "approvals": {}})
    print(f"started {a.file}: {len(questions)} questions for {a.domain}")


def cmd_next(a: argparse.Namespace) -> None:
    s = load(a.file)
    open_qs = [q for q in s["questions"] if q["id"] not in s["answers"]]
    open_qs.sort(key=lambda q: (q.get("priority", 2), q["id"]))
    if not open_qs:
        print("every question is answered")
        return
    for q in open_qs[: a.n]:
        print(f"{q['id']}  [{q['topic']}] {q['text']}")
    print(f"{len(open_qs)} unanswered")


def cmd_answer(a: argparse.Namespace) -> None:
    s = load(a.file)
    if a.qid not in {q["id"] for q in s["questions"]}:
        raise SessionError(f"no question {a.qid!r}; see `session.py next`")
    if not a.text.strip():
        raise SessionError("an empty answer isn't an answer; leave the question open instead")
    s["answers"][a.qid] = {"text": a.text.strip(), "source": a.source}
    save(a.file, s)
    print(f"answered {a.qid}")


def cmd_assume(a: argparse.Namespace) -> None:
    s = load(a.file)
    s["assumptions"].append({"id": f"A{len(s['assumptions']) + 1}", "text": a.text, "risk": a.risk, "validated": False})
    save(a.file, s)
    print(f"recorded A{len(s['assumptions'])}")


def cmd_decide(a: argparse.Namespace) -> None:
    s = load(a.file)
    refs = [r for r in a.from_.split(",") if r]
    missing = [r for r in refs if r not in s["answers"] and r not in {x["id"] for x in s["assumptions"]}]
    if not refs or missing:
        raise SessionError("a decision must cite answered questions or recorded assumptions"
                           + (f"; not found or unanswered: {', '.join(missing)}" if missing else ""))
    did = f"D{len(s['decisions']) + 1}"
    s["decisions"].append({"id": did, "text": a.text, "from": refs, "kind": a.kind})
    save(a.file, s)
    print(f"recorded {did} (proposed until approved)")


def cmd_option(a: argparse.Namespace) -> None:
    s = load(a.file)
    if not a.evidence:
        raise SessionError("an option needs at least one piece of evidence (--evidence); popularity alone isn't one")
    s["options"].append({"question": a.question, "name": a.name, "evidence": a.evidence, "cost": a.cost,
                         "constraint_fit": a.fits or []})
    save(a.file, s)
    print(f"recorded option {a.name!r} for {a.question!r}")


def cmd_approve(a: argparse.Namespace) -> None:
    s = load(a.file)
    if a.did not in {d["id"] for d in s["decisions"]}:
        raise SessionError(f"no decision {a.did!r}")
    if not a.by.strip():
        raise SessionError("an approval needs a named approver (--by)")
    s["approvals"][a.did] = a.by
    save(a.file, s)
    print(f"{a.did} approved by {a.by}")


def render_prd(s: dict) -> str:
    q = {x["id"]: x for x in s["questions"]}
    ans = s["answers"]

    def answered(topic: str) -> list[str]:
        return [f"- {ans[i]['text']} *({i})*" for i in sorted(ans) if q.get(i, {}).get("topic") == topic]

    lines = [f"# {s['title']}: product requirements", "",
             "Generated by the idea-developer skill from the session file; every line cites the answer it comes from.", ""]
    for title, topic in (("Goal", "goal"), ("Actors", "users"), ("Outcomes", "outcomes"), ("Constraints", "constraints"),
                         ("Out of scope", "scope")):
        body = answered(topic)
        lines += [f"## {title}", "", *(body or ["- *Not answered yet.*"]), ""]
    lines += ["## Decisions", ""]
    for d in s["decisions"]:
        state = f"approved by {s['approvals'][d['id']]}" if d["id"] in s["approvals"] else "**proposed, not approved**"
        lines.append(f"- **{d['id']}** {d['text']} — from {', '.join(d['from'])}; {state}")
    if not s["decisions"]:
        lines.append("- *None yet.*")
    lines += ["", "## Options considered", ""]
    for o in sorted(s["options"], key=lambda o: (o["question"], o["name"])):
        lines.append(f"- **{o['question']}: {o['name']}** (cost {o['cost']}): " + "; ".join(o["evidence"]))
    if not s["options"]:
        lines.append("- *None recorded.*")
    lines += ["", "## Assumptions", ""]
    for x in s["assumptions"]:
        lines.append(f"- **{x['id']}** {x['text']}" + (f" — risk: {x['risk']}" if x.get("risk") else "")
                     + ("" if x["validated"] else " *(unvalidated)*"))
    if not s["assumptions"]:
        lines.append("- *None recorded.*")
    open_qs = [x for x in s["questions"] if x["id"] not in ans]
    lines += ["", "## Open questions", ""]
    lines += [f"- {x['text']} *({x['id']})*" for x in sorted(open_qs, key=lambda x: (x.get("priority", 2), x["id"]))] or ["- *None.*"]
    return "\n".join(lines) + "\n"


def cmd_prd(a: argparse.Namespace) -> None:
    text = render_prd(load(a.file))
    if a.output:
        Path(a.output).write_text(text, encoding="utf-8")
        print(f"wrote {a.output} (sha256 {hashlib.sha256(text.encode()).hexdigest()[:12]})")
    else:
        sys.stdout.write(text)


def cmd_handoff(a: argparse.Namespace) -> None:
    s = load(a.file)
    pending = [d["id"] for d in s["decisions"] if d["id"] not in s["approvals"]]
    must = [x["id"] for x in s["questions"] if x.get("priority", 2) == 1 and x["id"] not in s["answers"]]
    if not s["decisions"]:
        raise SessionError("nothing to hand off: record and approve at least one decision")
    if pending or must:
        raise SessionError("not ready for Ananke: "
                           + "; ".join(filter(None, [pending and f"unapproved decisions {', '.join(pending)}",
                                                     must and f"unanswered priority questions {', '.join(must)}"])))
    goal = next((s["answers"][q["id"]]["text"] for q in s["questions"] if q["topic"] == "goal" and q["id"] in s["answers"]), s["title"])
    args = ["ananke", "spec", "create", "--title", s["title"], "--body", goal]
    for d in s["decisions"]:
        args += ["--acceptance", d["text"]]
    print(" ".join(shlex.quote(x) for x in args))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--file", type=Path, default=Path("idea-session.json"))
    sub = p.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("init"); x.add_argument("--title", required=True); x.add_argument("--domain", required=True); x.add_argument("--force", action="store_true")
    x = sub.add_parser("next"); x.add_argument("-n", type=int, default=5)
    x = sub.add_parser("answer"); x.add_argument("qid"); x.add_argument("text"); x.add_argument("--source", default="interview")
    x = sub.add_parser("assume"); x.add_argument("text"); x.add_argument("--risk", default="")
    x = sub.add_parser("decide"); x.add_argument("text"); x.add_argument("--from", dest="from_", required=True); x.add_argument("--kind", default="scope")
    x = sub.add_parser("option"); x.add_argument("question"); x.add_argument("--name", required=True); x.add_argument("--evidence", action="append"); x.add_argument("--cost", default="unknown"); x.add_argument("--fits", action="append")
    x = sub.add_parser("approve"); x.add_argument("did"); x.add_argument("--by", required=True)
    x = sub.add_parser("prd"); x.add_argument("-o", "--output")
    sub.add_parser("handoff")
    a = p.parse_args(argv)
    try:
        globals()[f"cmd_{a.cmd}"](a)
    except SessionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
