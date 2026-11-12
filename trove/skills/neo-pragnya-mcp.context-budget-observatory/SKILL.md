---
name: context-budget-observatory
description: "Measure whether code-graph context is worth its tokens in a repository: answer a fixed question set at several token budgets, find the smallest budget that reaches the best recall, list questions nothing finds, and track regressions between runs. Use for token budgets, context cost, retrieval quality, 'how many tokens does our assistant need', or checking that a change didn't make code search worse."
---

# Context budget observatory

Uses Ananke Plexus (`ananke context observe`). Nothing leaves the machine.

## Steps

1. Write 10 to 30 questions people really ask about the code, each with the symbols a good answer must name:

   ```json
   [{"question": "how are refunds approved", "expect": ["approve_refund"]},
    {"question": "where is the invoice total rounded", "expect": ["round_total", "Invoice"]}]
   ```

2. Measure and record:

   ```bash
   uvx --from ananke-plexus ananke context observe questions.json --record
   ```

3. Read the table: recall, tokens, the full-file baseline and recall per thousand tokens at each budget. The
   **knee** is the smallest budget with the best recall; set your assistant's budget there.
4. Questions *found at no budget* are the useful ones: rename the code, add a docstring, or fix the question.
5. Run it again after big changes. *Since the previous run* lists questions whose recall dropped or whose cost rose
   by more than a fifth.

## Rules

- Keep the question set fixed between runs, or the comparison means nothing; add new questions in a new file.
- Recall counts expected symbols, not answer quality; read a few answers yourself.
