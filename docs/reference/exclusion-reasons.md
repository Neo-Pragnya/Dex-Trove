---
title: Exclusion reasons
description: Every reason a candidate can be refused, with examples and what to do about it.
---

# Exclusion reasons

Each refused candidate is recorded in `trove/EXCLUDED.json` with one of these reasons. The checks run in this
order, and the first failure wins.

| Reason | Meaning | Example `detail` | What to do |
| --- | --- | --- | --- |
| `invalid-name` | Name can't be slugified into Ananke's name rule | the raw name | Fix upstream, or add an adapter-level rename |
| `name-collision` | Another item of the same kind and namespace already has this name | `up/foo already learned` | Usually two upstream items differ only by case or punctuation; report upstream |
| `license-denied` | Deny-verdict or unknown licence (item, frontmatter, nested file or no licence at all) | `LicenseRef-Proprietary — skills/docx/LICENSE.txt: restrictive terms (…)`; `unknown — no licence found`; `bundled GPL-3.0-only — …` | Nothing, unless the classification is wrong (then open an issue with the text) |
| `license-review` | Review-verdict licence (MPL, EPL, LGPL, CC-BY-SA) and the source hasn't opted in | `CC-BY-SA-4.0 — LICENSE: CC BY-SA text` | Decide per source; set `license.allow_review: true` and record why |
| `missing-entry` | The entry file was withheld (e.g. by an `exclude` glob) | `SKILL.md` | Fix the glob |
| `size` | A file > 5 MB or the item > 20 MB | the offending files | Withhold large assets with `exclude` if the item still works without them |
| `secret` | A real-format credential (AWS key, private key with material, GitHub/Slack/OpenAI/Anthropic/Google token) | `aws-access-key in cfg.env` | Report upstream; never allow-list a real secret |
| `duplicate` | Same entry file bytes as an item from a higher-priority source | `same content as anthropic/skill-creator` | Expected for aggregators; nothing to do |
| `out-of-scope` | Plugin with no admissible skill/agent members (e.g. canvas-only UI extensions) | `plugin has no admissible skill/agent members` | Nothing; Dex ships agent artifacts, not UI apps |

## Not exclusions

These are recorded on the item, not in `EXCLUDED.json`:

| Signal | Where | Meaning |
| --- | --- | --- |
| `secret_flags` / tag `ananke-secret-flag` | `dex.json` | Ananke's broader scanner would refuse the item (usually placeholders). `dex ananke sync` skips it by default. |
| `executes_code` / tag `executes-code` | `dex.json` | Contains scripts or `hooks.json` |
| `notes` | `dex.json` | Skipped symlinks; files withheld by `exclude` globs |

## 0.1.0 summary

| Source | Reason | Count |
| --- | --- | --- |
| awesome-copilot | out-of-scope (canvas-only plugins) | 32 |
| anthropic | license-denied (proprietary: docx, pdf, pptx, xlsx) | 4 |
| anthropic | license-denied (no licence: doc-coauthoring) | 1 |
