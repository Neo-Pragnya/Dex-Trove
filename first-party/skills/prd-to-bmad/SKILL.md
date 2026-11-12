---
name: prd-to-bmad
description: "Turn an approved PRD into traceable contracts before building: map every requirement to features, acceptance ids and tests, refuse a PRD that isn't approved or consistent, then compile BMAD behaviour, model and architecture contracts per requirement linked to the PRD revision. Use for spec-driven development, PRD to tasks, acceptance criteria traceability, BMAD contracts or 'are these requirements ready to build'."
---

# From an approved PRD to BMAD contracts

Uses Ananke Plexus (`ananke spec map`, `ananke spec compile`) on the PRD format Dev Guru's `dev spec new` writes.

## Steps

1. Write or update the PRD with `dev spec new "Name"`: requirements as `- **R1** ...` (optionally under
   `### Feature` headings) and acceptance lines as `- R1: how a reviewer sees it works`.
2. After review, set `status: approved` in its front matter (and `approved_by`).
3. Map it: `uvx --from ananke-plexus ananke spec map docs/prd.md`. Each criterion gets an id (`AC-R1-1`), the test
   that will be generated for it and the tests that already mention it. Exit 1 means it isn't consistent: fix what
   the findings say (a requirement with no criterion, a repeated id, a criterion naming no requirement).
4. Optionally describe the API first: `ananke triage api-contract --out contract`.
5. Compile: `ananke spec compile docs/prd.md --out .ananke/specs/bmad --api-contract contract/model-contract.yaml`.
   Requirements that name an operation (`POST /orders`, `/orders/{id}`) get its schemas in their model contract.
6. Build against the behaviour tests, name `AC-R1-1` in the test that checks it, and after implementation run
   `ananke spec map docs/prd.md --require-tests`.

## Rules

- Don't compile a draft for real work; `--draft` is for previewing.
- `bmad-index.json` links every file to the PRD's sha256: change the PRD, and compile again.
