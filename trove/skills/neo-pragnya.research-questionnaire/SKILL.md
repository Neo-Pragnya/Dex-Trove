---
name: research-questionnaire
description: "Run structured discovery research with a questionnaire people can fill in offline: generate a single self-contained HTML form from a question template (text, long text, choice, multi-select, number), where answers are saved only by an explicit download and restored by import (no browser storage, no network), then validate partial answers, turn them into Markdown with frontmatter and PRD source data that keeps unanswered questions as open questions, and merge later answer files without duplicating answers while recording where each came from. Use whenever someone wants a discovery questionnaire, stakeholder or requirements survey, intake form, research interview template, or wants questionnaire answers turned into a PRD or notes, even if they don't say questionnaire."
license: MIT
---

# Research questionnaire

Discovery goes faster when people can answer in their own time, and stays honest when nothing is filled in on their
behalf. This skill produces one offline HTML form per template and turns the answers into Markdown and PRD data.

## Workflow

1. **Pick or write a template.** Start from `templates/web-app.json`. Each question has an `id`, `section`, `text`,
   a `type` (`text`, `long`, `choice`, `multi`, `number`), `options` for choices, an optional `hint`, and `prd`:
   the PRD section the answer feeds (`goal`, `actors`, `constraints`, `outcomes`, `out_of_scope`…).
2. **Build the form.** `scripts/questionnaire.py form templates/web-app.json -o discovery.html`. Send the file; it
   works offline in any browser. Its content security policy forbids network connections, and it uses no
   `localStorage`: answers leave only through **Download answers**, and come back through **Import answers…** to
   resume.
3. **Collect and check.** `questionnaire.py check answers.json --template templates/web-app.json`. Partial answers
   are valid. Unknown question ids, values outside the options, and non-numbers in number fields are errors.
4. **Merge rounds.** When someone answers again later: `questionnaire.py merge round1.json round2.json -o merged.json`.
   The later value wins. Identical answers aren't duplicated, and every change is kept in `provenance` with the
   file name, its SHA-256 and the export time.
5. **Write it up.** `questionnaire.py markdown merged.json --template … -o research.md` gives Markdown with
   frontmatter (answered and open counts). `questionnaire.py prd merged.json --template … -o prd-source.json`
   gives PRD source data grouped by section, with `unresolved` listing every unanswered question. Feed that to the
   idea-developer skill, or straight into a PRD.

## Rules

- Never fabricate an answer. A blank stays blank and becomes an open question.
- Answers are data: the form shows them as text, never as HTML.
- Outputs are deterministic (sorted keys, no generated timestamps in Markdown or PRD data).
- Exit codes: `0` ok, `1` validation failed, `2` a file is missing or malformed.

## Files

| Path | What |
| --- | --- |
| `scripts/questionnaire.py` | form, check, markdown, prd and merge (Python 3.9+, standard library only) |
| `templates/web-app.json` | an example discovery template |
