---
name: scaffold-harvesting
description: "Harvest a reusable project template from a repository you're allowed to reuse: detect its layout and key technologies without copying anything, then build a versioned template from structural files only (build and tool configs, CI workflows, ignore files, folder layout), with the project name turned into variables, refusing secret-shaped text, .env files, proprietary or confidential files and non-permissive licences; render it into a new project and run the template's test in an isolated folder with no inherited secrets. Nothing is published automatically; reviewed templates go to Dex Trove through its candidate gate. Use whenever someone wants to turn a repo into a starter or template, extract a project skeleton or boilerplate, standardise new services on an existing layout, or make a cookiecutter or Copier-style template, even if they don't say scaffold."
license: MIT
---

# Scaffold harvesting

Good teams already have a project layout that works. This skill turns it into a template, without copying
application code, credentials or anything you aren't allowed to redistribute.

## Workflow

1. **Detect.** `scripts/harvest.py detect path/to/repo` reports the licence, technologies (Python, FastAPI,
   Node.js, React, Docker, GitHub Actions…), top-level folders and the structural files a template would use. It
   copies nothing.
2. **Check you may reuse it.** Templates are only built from permissively licensed code (MIT, Apache-2.0, BSD, ISC,
   Unlicense). For your own organisation's code, pass `--own`, and only if that's true.
3. **Build the template.**
   `harvest.py template path/to/repo -o templates/acme-api --name acme-api --version 1.0.0 --test "python -m pytest -q"`.
   - Only structural files are copied: `pyproject.toml`, `package.json`, tool configs, `Dockerfile`, CI workflows,
     ignore files and a fresh README skeleton. Folders become empty placeholders.
   - The project's name in every form (`acme-api`, `acme_api`, `Acme Api`, `AcmeApi`) becomes `{{project_name}}`,
     `{{package_name}}`, `{{project_title}}` or `{{project_class}}`.
   - Secret-shaped text refuses the whole template, and nothing is written. `.env` files and files marked
     proprietary or confidential are skipped and listed.
   - `template.json` records the name, version, source licence, technologies, variables, files and the test command.
4. **Test it.** `harvest.py test templates/acme-api --set project_name=demo` renders into a scratch folder and runs
   the declared test there, with a minimal environment (no inherited tokens or credentials).
5. **Use it.** `harvest.py render templates/acme-api -o ../billing-api --set project_name=billing-api`. Rendering
   fails if any variable has no value.
6. **Publish only through review.** Nothing here publishes. To share a template through Dex Trove, wrap it in a
   skill folder (a `SKILL.md` that explains when to use it, plus the template), then use the reviewed candidate gate:
   `dex candidate check`, `dex candidate review --approve`, then `dex candidate publish --to <source>`. Bump
   `--version` for every change, so locked users keep the version they tested.

## Rules

- Never copy application code, data or credentials into a template.
- Respect licences. When in doubt, don't harvest; ask the owner.
- Exit codes: `0` ok, `1` the template's test failed, `2` refused or bad input (the message says why).

## Files

| Path | What |
| --- | --- |
| `scripts/harvest.py` | detect, template, render and test (Python 3.9+, standard library only) |
