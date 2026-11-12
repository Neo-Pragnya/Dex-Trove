---
name: review-to-fix-loop
description: "Take a proposed patch from review to a pull request safely: apply it in a throwaway git worktree, run the tests it reaches, measure the risk delta (graph relationships, contract findings, complexity), approve the exact result by its digest, then commit to a new branch and open the PR with evidence. Use for applying a suggested fix, verifying a patch from review or an assistant, 'is this change safe', or turning a diff into a PR."
---

# Review-to-fix loop

Uses Ananke Plexus (`ananke triage patch`) for the checks and the Dex GitHub MCP server (`dex mcp serve github`)
for the pull request. The working tree you're in is never touched.

## Steps

1. Save the patch as a unified diff: `git diff > fix.patch`, or the suggestion from review.
2. Evaluate it:

   ```bash
   uvx --from ananke-plexus ananke triage patch fix.patch --run-tests
   ```

   It applies the patch in a throwaway worktree at `--base` (default `HEAD`), lists the tests the change reaches
   and runs them against the patched code, and compares relationships, contract findings and complexity before
   and after. It prints an **approval digest**.
3. Read the risk list with the person who owns the change. A rise in complexity or a new link between components
   isn't a failure, but it should be a decision.
4. When they approve, commit exactly what was evaluated:

   ```bash
   ananke triage patch fix.patch --run-tests --approve sha256:… --branch fix/order-totals -m "Fix order totals"
   ```

   A different digest, a patch that changed, or tests that didn't pass are refused.
5. Open the pull request with the `github` MCP tools: `github_pr_preview`, then `github_pr_create` with the
   approval digest the server asks for, and attach the evaluation JSON as evidence.

## Rules

- Never commit a patch whose tests weren't run; "to run" isn't "passed".
- Don't edit the patch after approval; evaluate it again.
