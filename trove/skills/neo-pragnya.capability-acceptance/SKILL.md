---
name: capability-acceptance
description: "Behaviour-level acceptance testing and a release gate for any CLI tool or Python package. Gherkin scenarios (behave-style, pytest-bdd) drive the real commands in sandbox projects with isolated HOME, a capability catalog marks what blocks a release, and the gate decides PROMOTE / CONDITIONAL / BLOCK with evidence and CLI-surface coverage. It includes adversarial probes with legitimate twins, runtime-generated fake credentials, testing of the built wheel in a fresh venv, real-Chrome browser journeys for the project's website (Playwright-style, no extra dependency) and CI wiring. Use whenever someone wants to test all capabilities or features of a package or CLI before release, add end-to-end, acceptance, BDD, behave, Gherkin, smoke or Playwright-like tests, build a release or quality gate, check that what ships (the wheel) really works, find bugs the unit tests miss, or asks 'what checks should run before we publish', even if they don't say acceptance."
---

# Capability acceptance

Unit tests prove the parts. This proves the **product**: install what ships, point it at a realistic project, use
each capability the way a person or an agent would, and decide whether the build may be released. The approach
comes from an agent-evaluation harness (the WWI course, Week 12) and was proven on Ananke Plexus and Dex Trove. In
its first runs it found 12 real bugs:
- success marks on failures, crashes on bad input, credentials that `git add -A` would commit, an MCP server that
  MCP clients couldn't talk to, and a quality gate passing when no tests ran;
- non-idempotent learning, installs that refused but exited 0, and a wheel-only path bug.

## The method

1. **Expected behaviour, not snapshots.** Assert exit codes, files, JSON fields, refusals and explanations, not
   wording that is free to change.
2. **Probe before you assert.** Run the real commands with `scripts/probe.py` (sandboxed, flags `CRASH` and
   `SUCCESS-MARK-ON-FAILURE` automatically) and read the output critically. Something wrong is a *finding*: write
   the correct expectation and tag it `@known_issue` (a strict xfail). Never encode the bug.
3. **Capabilities, not commands.** List what users rely on in `capabilities.yaml`. Mark `blocker: true` only for
   capabilities a release must never ship without. Every scenario tags the capabilities it proves (`@cap_<id>`).
4. **Attack probes have legitimate twins.** Every `@adversarial` scenario (leaked credential, code that must never
   run, an unsafe install) sits next to a clean case that must still work.
5. **Test what ships.** `make acceptance-wheel` builds the wheel, installs it with its extras into a fresh venv and
   runs the suite from there. Dev installs hide path and packaging bugs.
6. **The gate decides.** PROMOTE when everything passes. CONDITIONAL for known issues, unverified items,
   non-blocker gaps or CLI coverage below target. BLOCK when a blocker fails or has no scenario. The release
   workflow runs it on the exact artifact before publishing.

## Workflow

1. `python scripts/scaffold_acceptance.py <repo> --product "Name" --bin <cli> [--bin <cli2>] --version-file src/pkg/__init__.py --makefile --workflow`
   writes `acceptance/` with the harness, a catalog, a smoke feature, a fixture project, a README, Makefile targets
   and a CI workflow. It discovers the CLI surface by walking `--help`.
2. Fill `capabilities.yaml`: 8–25 capabilities, with blockers. Make the fixture project look like a real user's
   repo. A second fixture is fine, for example a maintainer checkout or upstream repos.
3. Probe each area. Write the commands to a file, then `python scripts/probe.py commands.txt --bin .venv/bin --fixture acceptance/fixtures/projects/sample`.
4. Write one feature file per area (`features/NN_<area>.feature`). Start with the happy path, then refusals,
   adversarial probes with twins, idempotency (run twice, nothing changes), and clean errors (`it fails cleanly`).
5. Run `make acceptance` (about 1–2 min with `-n auto`), read `acceptance/report/summary.md`, fix the product or
   the assertion, and repeat. Then run `make acceptance-wheel`.
6. Add browser journeys if the project has a website: adapt `assets/examples/dex_trove_journeys.mjs`. It covers a
   static server at the base path, real Chrome via CDP, search, item pages, diagram render and hover, theme, 404,
   phone width and console errors. Run it serially after the site builds, and let a failure block the deploy.
7. Wire CI. `acceptance.yml` runs on push and PR, and in `release-*.yml` the publish job `needs:` an acceptance job
   that runs `make acceptance-dist` on the downloaded artifact. Disable caches in tag-triggered jobs.

## Step vocabulary (assets/harness.py)

| Given | When | Then |
| --- | --- | --- |
| `a fresh project` · `a fresh project from fixture "x"` · `an empty directory` | `I run "cmd"` | `it succeeds` · `it fails` · `it fails cleanly` · `the exit code is N` · `it does not crash` |
| `the fixture "x" is copied to "dest"` | `I run "cmd" with input:` (docstring = stdin) | `the output contains / does not contain "t"` · `matches "re"` · `contains each of:` |
| `the file "p" with content:` | `I run:` (docstring = script) | `the file "p" exists / does not exist / contains / does not contain "t"` · `a file matching "glob" exists` |
| `the file "p" with content containing a fake "aws-access-key" credential:` (`{credential}` placeholder) | | `the JSON output at "a.b[0]" equals / contains V` · `has at least N items` |
| `I have run "cmd"` · `the environment variable "K" is "V"` · `the changes are committed` | | `the JSON file "glob" at "path" equals / contains V` · `it finishes within N seconds` · `the path "$SANDBOX/x" does not exist anywhere` |

Tags: `@cap_<id>`, `@known_issue`, `@adversarial`, `@slow`, `@needs_network` (skipped with
`ACCEPTANCE_OFFLINE=1`), `@needs_chrome`, `@needs_site` (runs when `ACCEPTANCE_SITE_DIST` is set).
Credential kinds: `aws-access-key`, `aws-secret-key`, `github-token`, `slack-token`.

## Gotchas

- `harness.py` is shared. When several repos vendor it, keep the copies byte-identical, with one repo as the
  source of truth. If line lengths differ, exclude the copy from the formatter.
- Gherkin keeps `\"` and `\n` literally. Assert on JSON paths or docstrings instead of escaped quotes.
- `@known_issue` is strict. When the bug is fixed, the scenario fails until you remove the tag. That's the point.
- Browser journeys are timing-sensitive under parallel CPU load. Run them serially (a separate make target).
- Never commit secret-shaped strings, not even fake ones. Scanners and push protection flag them, so generate them
  at runtime.
- `--import-mode=importlib` repos need the `sys.path.insert` that the conftest template already has.
- Clear `dist/` before building, and pick the newest wheel (`ls -t`). Otherwise the suite can test the *previous*
  release. The version scenario then fails and the gate blocks, which is good, but it costs a confusing run.

## Files

| Path | What |
| --- | --- |
| `assets/harness.py` | sandbox, steps, credential generator, release gate, Markdown/JSON reports, CI summary |
| `scripts/scaffold_acceptance.py` | create `acceptance/` in a repo (discovers the CLI surface from `--help`) |
| `scripts/probe.py` | run commands in a sandbox and flag crashes and success marks on failures |
| `assets/templates/` | capabilities.yaml, conftest.py, test loader, README, Makefile snippet, acceptance.yml |
| `assets/examples/` | real features (registry, security probes, MCP JSON-RPC, install safety, learn pipeline) and the Dex Trove browser journeys |
| `references/methodology.md` | where the ideas come from, a bug-pattern checklist and gate semantics |
