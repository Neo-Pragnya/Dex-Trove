# Security Policy

## Supported versions

Pre-1.0 releases receive best-effort fixes on the latest minor version.

## Reporting a vulnerability

Please report vulnerabilities **privately** through GitHub's
[private vulnerability reporting](https://github.com/Neo-Pragnya/Dex-Trove/security/advisories/new) and include:

- the affected version (and trove item, if relevant)
- reproduction steps
- an impact assessment
- a suggested remediation, if you have one

Do not open public issues for active vulnerabilities.

## What counts as a vulnerability here

Dex Trove has two very different surfaces:

| Surface | Examples | How to report |
| --- | --- | --- |
| **The `dex` package** (`src/dex_trove`) | path traversal while copying items, a learn guard that can be bypassed, an installer that writes outside its target, unsafe archive or git handling | Private advisory (above) |
| **Trove content** (`trove/`) | an item that contains a real credential, malicious instructions or scripts, or content whose licence we misclassified | Private advisory for credentials or malicious content; a normal issue for licence corrections |

## How trove content is handled

- Upstream content is **untrusted**. Dex never executes it: `learn` only reads and copies, and `install` only copies.
- Items containing scripts are tagged `executes-code`. Hooks (which run automatically in the host tool) are not
  installed without `--allow-exec`.
- Learn-time guards exclude items with real-format credentials (AWS keys, private keys, GitHub/Slack/OpenAI/
  Anthropic/Google tokens). Credential-*shaped* placeholders that Ananke's stricter scanner would refuse are
  recorded as `secret_flags` and skipped by `dex ananke sync` unless `--include-flagged` is passed.
- The docs site renders upstream Markdown through `rehype-sanitize`.
- CI scans the package with Trivy (blocking on CRITICAL/HIGH), Semgrep, pip-audit, CodeQL and gitleaks.
  `trove/` is scanned separately by Trivy (non-blocking, uploaded to the Security tab), because it is
  redistributed content, not code that Dex installs or runs.

See [docs/concepts/security-model.md](docs/concepts/security-model.md) for the full model.
