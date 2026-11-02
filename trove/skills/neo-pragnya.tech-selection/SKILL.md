---
name: tech-selection
description: "Choose a framework, library, database or service from evidence instead of popularity, and record the decision: compare two or more options against licence, platform and cost constraints, cite benchmarks, docs, security notes and team experience, check every citation resolves (including approved enterprise architecture documents), flag licence mismatches, require a named owner for any policy exception, and write a deterministic technology decision record with alternatives and trade-offs for human review. Use whenever someone asks which library, framework, database, queue, cloud service or tool to use, wants to compare technologies, needs a technology decision record or a policy exception, or asks whether a dependency's licence fits, even if they don't say decision record."
license: MIT
---

# Tech selection

A good technology choice can be explained a year later: what was compared, against which constraints, on what
evidence, and who decided. This skill builds that record, and refuses the usual shortcuts.

## Workflow

1. **Frame the question and constraints.** Copy `references/request.example.json`. Fill in `question`, `context`
   and `constraints`: allowed licences (your organisation's list, not a guess), required platforms, maximum cost,
   and anything else that's non-negotiable.
2. **Collect at least two options.** For each, add the licence (from its licence file, not from memory), the
   platforms, the cost, pros and cons, and **evidence**. Each piece of evidence needs a `kind` (`benchmark`, `doc`,
   `security`, `experience` or `popularity`) and a `cite` that resolves: an https URL, or a local document such
   as an approved architecture note (`docs/architecture.md#queues`). When the facts may be out of date, say so in
   the claim and cite the version you checked.
3. **Cite the enterprise architecture.** List approved architecture documents in `enterprise_docs`. The check
   fails if they can't be found.
4. **Check.** `scripts/decide.py check request.json` reports:
   - **refused**: an option without evidence, a citation that doesn't resolve, fewer than two options, a choice
     backed only by popularity, or a chosen option that breaks a constraint without an exception;
   - **flagged**: licences outside the allowed list, platform gaps and cost overruns, for every option.
5. **Exceptions need an owner.** If the best option breaks a constraint, add
   `{policy: "licence"|"platforms"|"cost", reason, owner, expires}`. An exception without an owner is refused.
6. **Write the record.** `scripts/decide.py record request.json -o docs/decisions/job-queue.md` writes context,
   constraints, an options table with cited evidence, trade-offs, enterprise references, flags and exceptions. With
   `chosen: null` it's a **proposal** for review. A person sets `chosen` and `decided_by`; the skill never decides
   on its own.

## Rules

- Popularity is a signal, never a reason. A choice needs at least one non-popularity piece of evidence.
- Don't invent licences, benchmarks or citations. Unknown stays unknown, and is flagged.
- The record is deterministic: the same request gives the same file, so diffs show real changes.
- Exit codes: `0` ok, `1` checks failed (each reason printed), `2` the request is missing or malformed.

## Files

| Path | What |
| --- | --- |
| `scripts/decide.py` | check and record (Python 3.9+, standard library only) |
| `references/request.example.json` | a complete example request |
| `references/architecture.md` | an example enterprise document the example cites |
