---
name: evidence-first-adr
description: "Write an architecture decision record whose options carry measured evidence instead of adjectives: code and tests each option reaches, hotspots it touches, new dependencies and their known vulnerabilities, and the team's own estimates labelled as assumptions, ranked by stated weights with the decision left to people. Use for ADRs, architecture decisions, comparing design options, trade-off analysis or 'which approach should we take', even if they don't say ADR."
---

# Evidence-first architecture decisions

Uses Ananke Plexus (`ananke arch decide`), which reads the repository and runs nothing.

## Steps

1. Write a decision file next to the code, one option per alternative. Name what each option would change in
   `touches` (files, folders or symbols) and any new packages in `adds_dependencies`. Put estimates you can't
   measure (effort, cost) under `assumptions`, each with its `source`.

   ```yaml
   title: Where order totals are computed
   context: Totals are computed twice and disagree on rounding.
   criteria: {impact: 2, risk: 3, cost: 1}   # weights; lower is better for every criterion
   options:
     - name: Compute in the service layer
       touches: [app/services/orders.py]
       assumptions: [{metric: effort_days, value: 2, source: team estimate}]
     - name: Compute in the database
       touches: [app/models.py, db/migrations]
       adds_dependencies: [sqlalchemy-utils]
   ```

2. For known vulnerabilities in new dependencies, run a dependency check first
   (`ananke triage findings --check-vulnerabilities`, or offline with `ananke cve import`). Without one, they
   show as *unknown*, never as safe.
3. Run `uvx --from ananke-plexus ananke arch decide decision.yaml -o docs/adr/0007-order-totals.md`.
4. Read the evidence table for each option. Every number says how it's known: *declared by the option*,
   *simulated* (from the code graph), *observed* (from the repository) or *assumed* (yours).
5. Discuss the ranking; it's a starting point. Record the choice, who made it and why under **Decision**, and
   change the status from *proposed* yourself.

## Rules

- Never present a simulated reach as an observed fact, or an assumption as a measurement.
- Don't add options to make the favourite look good: each needs the same evidence.
- If an option names files that aren't in the code graph, the report says so; fix the names before deciding.
