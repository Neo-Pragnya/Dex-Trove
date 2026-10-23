# Why package firewalls quarantine, and what to look at

## Reading the report you're given

| Report wording (varies by vendor) | Category | Where to look |
| --- | --- | --- |
| "Security vulnerability", CVE or GHSA id, "Severity ≥ High" | vulnerable dependency, or an *embedded* component | `scan.json → vulns`; for embedded JS or C code, the inventory's minified and binary lists |
| "Secret detected", "Credential", "Hardcoded key" | secrets | gitleaks findings, including the **sdist's** `tests/` |
| "License not approved", "Unknown license", "License conflict" | licence | `License-Expression` vs bundled texts; OFL and font files, CC-BY content, "JSON License" matches |
| "Suspicious", "Malicious", "Obfuscated code", "Install script", "Network access" | heuristics | GuardDog rules; minified JS; `setup.py` or `.pth` side effects; base64 blobs |
| "Component not found", "Unknown component", "Immature", "Low popularity" | operational risk | package age and downloads: no code fix |

Black Duck's **signature scan** matches files to known open-source projects. A vendored library (for example
`mermaid.min.js`) shows up as its own component, with its own licence and CVEs. Keep vendored files at versions
without advisories, and list them in the release notes. You can check a version against OSV:
`curl -d '{"package":{"name":"mermaid","ecosystem":"npm"},"version":"11.17.2"}' https://api.osv.dev/v1/query`.

## Patterns that caused real quarantines

- **Placeholder credentials in shipped docs or teaching content.** `sk_live_…`, `AKIA…` and `api_key = "<16 chars>"`
  all match, however obviously fake they are to a person. Exclude the content, or rewrite your own placeholders
  as `<YOUR_KEY>`.
- **Test fixtures in the sdist.** `tests/` ships in most sdists. Build fakes at runtime, or exclude `tests/` from
  the sdist.
- **A declared licence narrower than the contents.** A package that bundles third-party files must declare every
  licence in `License-Expression` (PEP 639) and ship the texts.
- **Archive extraction without a filter.** Use `tarfile.extractall(dest, filter="data")` (Python 3.11.4+), and
  validate member paths yourself on older versions.
- **Content libraries that ship third-party scripts.** These trip process-spawn, env-var and base64 rules. Keep
  them out of the importable package if you can, or split the content into its own distribution, so that the code
  package stays clean.
- **A broad allowlist in your own scanner config.** Allowlisting `trove/` or `tests/` wholesale makes your scans
  pass while the firewall's fail.

## Responding to a quarantine

1. Reproduce it with `scan_dist.py` on the exact published version.
2. Fix it and release a **new version**. PyPI never accepts the same filename twice, and a quarantined version
   stays quarantined.
3. Give the security team the new version, the `summary.md`, the CycloneDX SBOM, and the list of reviewed
   heuristic hits with a reason for each.
