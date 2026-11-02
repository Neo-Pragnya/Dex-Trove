---
name: idea-developer
description: "Turn a rough idea into an approved, traceable product requirement through a scoped interview: a question bank per domain (web app, data platform, AI agent, CLI tool), recorded assumptions with risks, decisions that must cite the answers they come from, competing options with evidence and cost, named approvals, a living PRD (actors, outcomes, out of scope, open questions) and a handoff to the Ananke spec lifecycle that is refused while anything is unapproved. Use whenever someone has an idea, a feature request or a vague brief and wants it scoped, wants a PRD or requirements, asks what questions to ask stakeholders, wants to compare approaches before building, or wants to start spec-driven development, even if they don't say PRD."
license: MIT
---

# Idea developer

Turns "we should build something like…" into a requirement a team can approve and a harness can execute, without
inventing anything along the way. The interview state lives in one JSON file, so it can pause and resume, and every
line of the resulting PRD cites the answer it came from.

## Workflow

1. **Scope the interview.** `scripts/session.py init --title "…" --domain web-app|data-platform|ai-agent|cli-tool`.
   The question bank (`references/questions.json`) has core questions (goal, actors, outcomes, out of scope,
   constraints, risks) plus domain ones. Priority-1 questions must be answered before handoff.
2. **Ask, a few at a time.** `session.py next -n 3` lists the most important unanswered questions. Ask them in
   plain language, then record the person's words: `session.py answer goal-1 "…"`. Never fill an answer yourself;
   if they don't know, leave it open. Open questions are part of the PRD.
3. **Record assumptions separately.** `session.py assume "…" --risk "…"`. An assumption is not an answer, and the
   PRD marks it *unvalidated*.
4. **Propose options with evidence.** For each real choice, record two or three options:
   `session.py option "Web stack" --name "…" --evidence "…" --cost low --fits "runs on our Azure tenant"`. An
   option needs evidence; popularity alone isn't any. Present them side by side, with trade-offs and the enterprise
   constraints each one fits.
5. **Decide, citing the source.** `session.py decide "…" --from goal-1,constraints-1` refuses decisions that
   cite nothing, or cite unanswered questions. Decisions stay **proposed** until approved.
6. **Get named approvals.** `session.py approve D1 --by "Product owner"`. Never approve on someone's behalf.
7. **Write the PRD.** `session.py prd -o PRD.md` renders actors, outcomes, constraints, out of scope, decisions with
   approval state, options considered, assumptions and open questions. The output is deterministic (no timestamps),
   so re-running it on the same session gives the same file.
8. **Hand off to Ananke.** `session.py handoff` prints an `ananke spec create --title … --body … --acceptance …`
   command (one acceptance criterion per approved decision). It refuses while any decision is unapproved or a
   priority-1 question is open. Run the printed command yourself; the script never runs it.

## Rules

- Keep interviews bounded: 3–5 questions per turn, and stop when priority-1 and -2 questions are answered.
  Speculative research belongs in options with evidence, not in answers.
- Every decision traces to answers or assumptions. If you can't cite one, ask another question first.
- Nothing unapproved appears as approved, in the PRD or the handoff.
- Errors are actionable: a missing session, an unknown domain, a malformed file, an empty answer and an uncited
  decision each say what to do next, with exit code 2.

## Files

| Path | What |
| --- | --- |
| `scripts/session.py` | the session CLI (Python 3.9+, standard library only) |
| `references/questions.json` | the question bank: core + per-domain questions with topics and priorities |
