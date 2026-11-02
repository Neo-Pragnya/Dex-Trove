#!/usr/bin/env python3
"""Research questionnaires: an offline HTML form, answers as JSON, Markdown and PRD data, and safe resume.

  questionnaire.py form templates/web-app.json -o form.html     # one offline file; save = explicit download
  questionnaire.py check answers.json --template templates/web-app.json
  questionnaire.py markdown answers.json --template … -o research.md   # with frontmatter; open questions listed
  questionnaire.py prd answers.json --template … -o prd-source.json    # PRD source data, unresolved questions kept
  questionnaire.py merge earlier.json later.json -o merged.json       # resume: no duplicates, provenance kept

The form never uses browser storage or the network (its CSP forbids connections): answers leave only through the
Download button, and come back through Import. Partial answers are valid; unanswered questions stay unanswered and
are never filled in. Python 3.9+, standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from pathlib import Path

TEMPLATE = "research-questionnaire/template@1"
ANSWERS = "research-questionnaire/answers@1"
TYPES = ("text", "long", "choice", "multi", "number")


class QError(Exception):
    pass


def read(path: Path, schema: str) -> dict:
    if not path.is_file():
        raise QError(f"{path} not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise QError(f"{path} is not valid JSON: {exc}") from exc
    if data.get("schema") != schema:
        raise QError(f"{path}: expected schema {schema!r}, found {data.get('schema')!r}")
    return data


def template(path: Path) -> dict:
    t = read(path, TEMPLATE)
    ids = [q["id"] for q in t.get("questions", [])]
    if len(ids) != len(set(ids)):
        raise QError(f"{path}: duplicate question ids")
    for q in t["questions"]:
        if q.get("type", "text") not in TYPES:
            raise QError(f"{path}: question {q['id']} has unknown type {q.get('type')!r}; use one of {', '.join(TYPES)}")
        if q.get("type") in ("choice", "multi") and not q.get("options"):
            raise QError(f"{path}: question {q['id']} needs options")
    return t


def validate(ans: dict, t: dict) -> list[str]:
    qs = {q["id"]: q for q in t["questions"]}
    problems = []
    if ans.get("template") != t["id"]:
        problems.append(f"answers are for template {ans.get('template')!r}, not {t['id']!r}")
    for qid, v in ans.get("answers", {}).items():
        q = qs.get(qid)
        if q is None:
            problems.append(f"unknown question {qid!r}")
        elif q.get("type") == "choice" and v not in q["options"]:
            problems.append(f"{qid}: {v!r} isn't one of the options")
        elif q.get("type") == "multi" and (not isinstance(v, list) or any(x not in q["options"] for x in v)):
            problems.append(f"{qid}: expects a list of the options")
        elif q.get("type") == "number" and not isinstance(v, (int, float)):
            problems.append(f"{qid}: expects a number")
    return problems


def answered(ans: dict) -> dict:
    return {k: v for k, v in ans.get("answers", {}).items() if v not in ("", None, [])}


def cmd_form(a: argparse.Namespace) -> None:
    t = template(Path(a.template))
    data = json.dumps(t).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    page = FORM.replace("{{TITLE}}", html.escape(t["title"])).replace("{{TEMPLATE}}", data)
    Path(a.output).write_text(page, encoding="utf-8")
    print(f"wrote {a.output}: {len(t['questions'])} questions, offline, saves only by download")


def cmd_check(a: argparse.Namespace) -> int:
    t = template(Path(a.template))
    ans = read(Path(a.answers), ANSWERS)
    problems = validate(ans, t)
    for p in problems:
        print(f"✗ {p}", file=sys.stderr)
    done = answered(ans)
    print(f"{len(done)} of {len(t['questions'])} answered" + ("" if problems else "; valid"))
    return 1 if problems else 0


def _value(v: object) -> str:
    return ", ".join(map(str, v)) if isinstance(v, list) else str(v)


def cmd_markdown(a: argparse.Namespace) -> int:
    t = template(Path(a.template))
    ans = read(Path(a.answers), ANSWERS)
    problems = validate(ans, t)
    if problems:
        raise QError("; ".join(problems))
    done = answered(ans)
    open_qs = [q for q in t["questions"] if q["id"] not in done]
    lines = ["---", f"title: {json.dumps(t['title'])}", f"template: {t['id']}", f"respondent: {json.dumps(ans.get('respondent', ''))}",
             f"answered: {len(done)}", f"open: {len(open_qs)}", "---", "", f"# {t['title']}", ""]
    for section in dict.fromkeys(q.get("section", "General") for q in t["questions"]):
        rows = [q for q in t["questions"] if q.get("section", "General") == section and q["id"] in done]
        if rows:
            lines += [f"## {section}", ""]
            for q in rows:
                lines += [f"**{q['text']}**", "", _value(done[q["id"]]), ""]
    lines += ["## Open questions", ""] + ([f"- {q['text']} *({q['id']})*" for q in open_qs] or ["- None."]) + [""]
    out = "\n".join(lines)
    Path(a.output).write_text(out, encoding="utf-8") if a.output else sys.stdout.write(out)
    return 0


def cmd_prd(a: argparse.Namespace) -> int:
    t = template(Path(a.template))
    ans = read(Path(a.answers), ANSWERS)
    problems = validate(ans, t)
    if problems:
        raise QError("; ".join(problems))
    done = answered(ans)
    by_topic: dict[str, list[dict]] = {}
    for q in t["questions"]:
        if q["id"] in done:
            by_topic.setdefault(q.get("prd", "notes"), []).append({"question": q["id"], "answer": done[q["id"]]})
    out = {"schema": "research-questionnaire/prd-source@1", "template": t["id"], "sections": by_topic,
           "unresolved": [q["id"] for q in t["questions"] if q["id"] not in done]}
    text = json.dumps(out, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    Path(a.output).write_text(text, encoding="utf-8") if a.output else sys.stdout.write(text)
    return 0


def cmd_merge(a: argparse.Namespace) -> int:
    """Later answers win, but nothing is lost: earlier values are kept as history with where they came from."""
    files = [Path(a.earlier), Path(a.later)]
    docs = [read(f, ANSWERS) for f in files]
    if docs[0].get("template") != docs[1].get("template"):
        raise QError("the two files answer different templates")
    merged = {"schema": ANSWERS, "template": docs[0]["template"], "respondent": docs[1].get("respondent") or docs[0].get("respondent", ""),
              "answers": {}, "provenance": {}}
    for f, d in zip(files, docs):
        digest = hashlib.sha256(f.read_bytes()).hexdigest()[:12]
        prior = d.get("provenance", {})
        for qid, v in answered(d).items():
            hist = merged["provenance"].setdefault(qid, [])
            for h in prior.get(qid, []):
                if h not in hist:
                    hist.append(h)
            entry = {"value": v, "file": f.name, "sha256": digest, "exported_at": d.get("exported_at", "")}
            if merged["answers"].get(qid) != v:
                merged["answers"][qid] = v
                hist.append(entry)
    Path(a.output).write_text(json.dumps(merged, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"merged {len(merged['answers'])} answers into {a.output}")
    return 0


FORM = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; form-action 'none'">
<title>{{TITLE}}</title>
<style>
:root{--ink:#1f1d2b;--muted:#5d5a72;--line:#e3e0ef;--bg:#faf8f3;--card:#fff;--accent:#5b4bd6}
@media (prefers-color-scheme:dark){:root{--ink:#ecebf5;--muted:#a3a1bb;--line:#2e2c40;--bg:#14131c;--card:#1c1b27;--accent:#9b8cff}}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,sans-serif}
main{max-width:760px;margin:0 auto;padding:24px 16px 80px}
h1{font-size:1.6rem;margin:0 0 4px}.lede{color:var(--muted);margin:0 0 20px}
fieldset{border:1px solid var(--line);background:var(--card);border-radius:12px;padding:14px 16px;margin:0 0 12px}
legend{font-weight:650;padding:0 4px}.hint{color:var(--muted);font-size:.9rem;margin:2px 0 8px}
input[type=text],input[type=number],textarea{width:100%;box-sizing:border-box;font:inherit;padding:8px;border:1px solid var(--line);border-radius:8px;background:transparent;color:inherit}
label.opt{display:block;padding:2px 0}h2{font-size:1.1rem;margin:24px 0 8px}
.bar{position:sticky;bottom:0;display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding:12px 16px;background:var(--card);border-top:1px solid var(--line)}
button{font:inherit;padding:8px 14px;border-radius:999px;border:1px solid var(--accent);background:var(--accent);color:#fff;cursor:pointer}
button.ghost{background:transparent;color:var(--accent)}#status{color:var(--muted);font-size:.9rem}
</style></head><body><main id="main"></main>
<div class="bar"><button id="save">Download answers (.json)</button><button class="ghost" id="load">Import answers…</button>
<input id="file" type="file" accept="application/json" hidden><span id="status" aria-live="polite"></span></div>
<script type="application/json" id="template">{{TEMPLATE}}</script>
<script>
(() => {
  const T = JSON.parse(document.getElementById("template").textContent);
  const main = document.getElementById("main"), status = document.getElementById("status");
  const el = (tag, props = {}, ...kids) => { const n = document.createElement(tag); Object.assign(n, props); n.append(...kids); return n; };
  main.append(el("h1", { textContent: T.title }), el("p", { className: "lede", textContent: (T.intro || "") + " Your answers stay in this page until you download them; nothing is sent anywhere." }));
  let section = null;
  for (const q of T.questions) {
    if ((q.section || "General") !== section) { section = q.section || "General"; main.append(el("h2", { textContent: section })); }
    const fs = el("fieldset", {}, el("legend", { textContent: q.text }));
    if (q.hint) fs.append(el("p", { className: "hint", textContent: q.hint }));
    const name = "q_" + q.id, type = q.type || "text";
    if (type === "choice" || type === "multi") {
      for (const o of q.options) fs.append(el("label", { className: "opt" }, el("input", { type: type === "choice" ? "radio" : "checkbox", name, value: o }), " " + o));
    } else if (type === "long") fs.append(el("textarea", { name, rows: 4 }));
    else fs.append(el("input", { type: type === "number" ? "number" : "text", name }));
    main.append(fs);
  }
  const collect = () => {
    const answers = {};
    for (const q of T.questions) {
      const els = [...document.getElementsByName("q_" + q.id)], type = q.type || "text";
      if (type === "multi") { const v = els.filter((e) => e.checked).map((e) => e.value); if (v.length) answers[q.id] = v; }
      else if (type === "choice") { const v = els.find((e) => e.checked); if (v) answers[q.id] = v.value; }
      else { const v = els[0].value.trim(); if (v !== "") answers[q.id] = type === "number" ? Number(v) : v; }
    }
    return answers;
  };
  const fill = (answers) => {
    for (const q of T.questions) {
      const els = [...document.getElementsByName("q_" + q.id)], v = answers[q.id], type = q.type || "text";
      if (type === "multi") els.forEach((e) => (e.checked = Array.isArray(v) && v.includes(e.value)));
      else if (type === "choice") els.forEach((e) => (e.checked = e.value === v));
      else els[0].value = v === undefined ? "" : String(v);
    }
  };
  document.getElementById("save").onclick = () => {
    const answers = collect();
    const body = { schema: "research-questionnaire/answers@1", template: T.id, respondent: "", exported_at: new Date().toISOString(), answers };
    const a = el("a", { href: URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], { type: "application/json" })), download: T.id + "-answers.json" });
    a.click(); URL.revokeObjectURL(a.href);
    status.textContent = Object.keys(answers).length + " of " + T.questions.length + " answered; saved as a download.";
  };
  document.getElementById("load").onclick = () => document.getElementById("file").click();
  document.getElementById("file").onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    try { const d = JSON.parse(await f.text()); if (d.schema !== "research-questionnaire/answers@1" || d.template !== T.id) throw new Error("not answers for this form"); fill(d.answers || {}); status.textContent = "Imported " + Object.keys(d.answers || {}).length + " answers from " + f.name + "."; }
    catch (err) { status.textContent = "Couldn't import: " + err.message; }
  };
})();
</script></body></html>
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("form"); x.add_argument("template"); x.add_argument("-o", "--output", required=True)
    for name in ("check", "markdown", "prd"):
        x = sub.add_parser(name); x.add_argument("answers"); x.add_argument("--template", required=True)
        if name != "check":
            x.add_argument("-o", "--output")
    x = sub.add_parser("merge"); x.add_argument("earlier"); x.add_argument("later"); x.add_argument("-o", "--output", required=True)
    a = p.parse_args(argv)
    try:
        rc = globals()[f"cmd_{a.cmd}"](a)
    except QError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return rc or 0


if __name__ == "__main__":
    sys.exit(main())
