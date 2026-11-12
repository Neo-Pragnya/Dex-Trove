---
name: test-gap-synthesis
description: "Find the tests a codebase is missing and write skeletons for them from evidence: partly taken branches in a coverage report, failing cases in JUnit XML and API operations whose handlers changed, each test citing the line it answers and failing until it's written. Use for test gaps, missing tests, improving coverage, branch coverage, regression tests after a failure or contract tests for changed endpoints."
---

# Test gap synthesis

Uses Ananke Plexus (`ananke triage test-gaps`). Generated tests are suggestions: each fails until a person writes
the assertion, so a gap is never reported as closed.

## Steps

1. Produce the evidence you have:
   - branch coverage: `pytest --cov --cov-branch --cov-report xml`;
   - failures: `pytest --junitxml junit.xml` (or your CI's JUnit report);
   - contract changes: a base revision, for example `main`.
2. Run:

   ```bash
   uvx --from ananke-plexus ananke triage test-gaps --coverage coverage.xml --junit junit.xml --base main \
     --write tests/test_gaps.py
   ```

3. Open `tests/test_gaps.py`. Each test names its evidence (`app/pricing.py:42`), why it exists (the condition
   whose other branch never ran, the failure message, the contract finding) and its target.
4. Write the assertion for each, starting with observed failures, then changed contracts, then branches in code
   you're changing. Delete a skeleton only with a reason in the review.
5. Re-run coverage and the command: the gaps you closed disappear.

## Rules

- Never replace `pytest.fail(...)` with `pass` to make a skeleton green.
- A branch that can't be reached is a finding about the code, not a test to fake.
