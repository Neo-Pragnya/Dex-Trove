---
name: api-contract-review
description: "Review an API's real contract from its code and OpenAPI files: auth, request and response shapes per operation with the file and line for each, a BMAD model contract, and findings such as missing error responses, auth with no 401/403, untested auth and code disagreeing with the spec. Use for API reviews, endpoint inventories, OpenAPI drift, auth coverage, contract tests or documenting an existing API."
---

# API contract review

Uses Ananke Plexus (`ananke triage api-contract`), which reads handlers (FastAPI, Starlette, Flask, aiohttp,
Tornado, Express, NestJS) and OpenAPI 3 or Swagger 2 files without running anything.

## Steps

1. `uvx --from ananke-plexus ananke triage api-contract --out contract` writes `api-contract.json`,
   `model-contract.yaml` and `api-contract.md`. Pass `--spec api/openapi.yaml` for a spec elsewhere.
2. Read the table: each operation's auth, request (path, query, header, body schema or the fields the handler
   reads) and responses. *Observed* facts are written down (a type, a `response_model`, the spec); *inferred* ones
   come from how the handler uses its input.
3. Work through the findings, high first: auth without 401/403, untested auth (no test calls it, or none checks the
   failed-auth response), auth the code and spec disagree on, missing error responses.
4. Generate contract tests from the spec with `ananke triage api-tests openapi.yaml`, and run them only against a
   service on this machine (`--run http://127.0.0.1:8000`).
5. Gate CI on it: `ananke triage api-contract --fail-on high`.

## Rules

- Frameworks listed as unsupported (Go, Spring, ASP.NET, Rails, Laravel, Rust) aren't read; describe them in an
  OpenAPI file rather than assuming they have no API.
- Auth applied to a whole app elsewhere isn't seen; confirm a "no auth" result in the code.
