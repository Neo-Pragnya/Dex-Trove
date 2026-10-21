# Methodology

## Lineage

The design comes from the WWI Data Science Agent course (Week 12), which evaluated an agent before promotion. It
carries over four ideas:

| Week 12 (agent evaluation) | Here (package / CLI acceptance) |
| --- | --- |
| Versioned cases state expected *behaviour* (grain, required tools, refusals), not expected strings | Gherkin scenarios assert exit codes, files, JSON fields, refusals |
| Scenario matrix: environment switches, `must` / `must_not` markers, expected error cells | Sandboxed scenarios with fixtures, `contains` / `does not contain`, `it fails cleanly` |
| Adversarial probes, each with a legitimate twin | `@adversarial` scenarios next to clean twins |
| Multi-dimensional release gate (PROMOTE / CONDITIONAL / BLOCK); blockers veto; every rule cites evidence | Capability catalog with blockers; the same three decisions; the report lists the scenarios behind each rule |

## Bug patterns worth a scenario in every CLI

These are what the first runs on two mature, unit-tested packages actually found:

1. **A success mark on a failure.** The output starts with ✓ and the exit code is non-zero. Use `it fails cleanly`.
2. **A crash on bad input.** An invalid enum value or the wrong file type gives a traceback instead of an error
   listing the valid values.
3. **Silent acceptance of an invalid value.** An unknown channel or category is stored as given.
4. **A refusal that exits 0.** Nothing was done, but scripts can't tell.
5. **Secrets that `git add -A` would commit.** Init writes credentials or local config inside the project without
   a `.gitignore`.
6. **Protocol claims that don't hold.** "MCP server" (or "OpenAPI", or "LSP") should be tested with the *official*
   client.
7. **A gate that passes when nothing ran.** Zero tests, zero items or zero files is a warning, never a pass.
8. **Non-idempotence.** Running twice on unchanged input changes the output.
9. **Wheel-only bugs.** Package-data paths, "am I in a checkout?" logic and missing extras show up only when the
   built wheel is installed.
10. **Accidental slowness.** Copying a whole checkout (`.venv`, `node_modules`) into a temp folder. Set
    `it finishes within N seconds` budgets on the main paths.
11. **Docs that disagree with the CLI.** Commands in infographics or READMEs that don't exist. Run every documented
    command.

## Gate semantics

```
capability status:  pass | fail | known_issue | unverified (all skipped) | missing (no scenario)
BLOCK        ← any blocker in fail or missing
CONDITIONAL  ← anything else not pass, or CLI surface coverage < surface_target
PROMOTE      ← otherwise
```

`--acceptance-require=promote` makes the session fail unless the decision is PROMOTE. Use it for strict release
trains. The default fails only on BLOCK.

## Sizing

Expect 30–70 scenarios for a mid-sized CLI, running in 1–2 minutes with `pytest-xdist`. Keep each scenario under
about 30 s. Mark slower ones `@slow`, and keep browser journeys and other timing-sensitive checks out of the
parallel pool.
