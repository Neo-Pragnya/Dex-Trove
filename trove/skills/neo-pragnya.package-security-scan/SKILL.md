---
name: package-security-scan
description: "Find out why a Python package gets quarantined, flagged or blocked by package firewalls and SCA tools (Black Duck, JFrog Xray or Curation, Sonatype Nexus Firewall, Snyk, Mend, Socket), and fix it with free tools instead of a subscription. It scans the exact built or published wheel and sdist: secrets with gitleaks, vulnerable dependencies with pip-audit, Grype or OSV, malicious-package heuristics with GuardDog, Bandit, licence metadata, and an inventory of scripts, binaries and minified JS. It produces a report, applies honest fixes (remove secret-shaped strings, declare every bundled licence, close real code issues), and adds a blocking dist-scan job to the release workflow. Use whenever someone says their package was quarantined, flagged, blocked or failed a security scan, asks for a security scan or report without a paid tool, wants an SBOM or pre-release security gate for PyPI, or asks what Black Duck or a package firewall will find, even if they don't say scan."
---

# Package security scan

Package firewalls judge the **files you publish**, not your repo. Proven on Ananke Plexus and Dex Trove, where
dependency CVEs were clean but the packages were quarantined. The causes were:
- credential-shaped placeholders in shipped content;
- fake keys in the sdist's tests;
- a declared licence of `MIT` while the package bundled Apache-2.0 and OFL-1.1 content;
- an unfiltered `tarfile.extractall`;
- heuristic hits on vendored minified JS and third-party scripts.

## 1. Get the evidence first

Ask for the scanner's **policy violation names**: one line each, such as "Secrets detected" or "License not
approved". They say which of the reasons below applies. While you wait, scan the published files yourself.
Download them with `curl` from `https://pypi.org/pypi/<name>/<version>/json`, because `pip download` refuses a
package whose `requires-python` excludes the local Python. Run the script on that directory:

```bash
python scripts/scan_dist.py --dist <dir-with-whl-and-tar.gz> --out scan-report [--extras all]
```

It needs `gitleaks` and `uv` (`brew install gitleaks`); pip-audit, GuardDog and Bandit come through `uvx`. It
writes `scan-report/summary.md` and `scan.json`, and exits 1 on any secret or vulnerable dependency.

For a second opinion, all free:
- `brew install grype syft osv-scanner trivy`, then `grype dir:<venv>` on an environment with the wheel installed.
- `trivy fs --scanners vuln,secret,license`.
- `osv-scanner`.

## 2. Map findings to quarantine reasons and fix honestly

| Reason a firewall quarantines | Check | Honest fix |
| --- | --- | --- |
| Secrets | gitleaks over wheel **and** sdist (tests ship in the sdist) | Remove the content, or build test fakes at runtime (`"AKIA" + "…"`). Allowlist only *reviewed* false positives (UUIDs, public IDs), narrowly, with the reason |
| Vulnerable dependencies | pip-audit over the tree the wheel resolves to, with the extras users install | `uv lock --upgrade-package X`, raise the lower bound, release a new version (never re-upload a version) |
| Licence | `License-Expression` vs what is bundled (fonts, vendored JS, copied content) | Declare the full expression (`MIT AND Apache-2.0 AND OFL-1.1`), ship the texts, add a test that keeps them in step |
| Malicious-code heuristics | GuardDog, Bandit HIGH | Fix real issues (path traversal, `shell=True` on input). Document expected hits (vendored minified JS, a deny-list containing `rm -rf /`) in the release notes |
| Immaturity or popularity | package age, downloads | Nothing in code: request an exception, or wait out the maturity window |

**Never disguise benign code to slip past a scanner.** That means no string splitting of `rm -rf`, no encoding of
URLs, and no hiding of files. It's evasion, and it makes the next reviewer's job harder. Remove the content, fix
it, or document it. Fake credentials built at runtime in *tests* are fine: they never ship as a credential-shaped
literal.

**Repo-history scans are a separate job.** Removing a placeholder from the tree doesn't remove it from history.
Pin each historical finding by fingerprint in `.gitleaksignore` (`commit:file:rule:line`), so anything new is still
reported. Never allowlist whole directories such as `tests/` or a vendored-content folder: that hides exactly
what a firewall will find.

## 3. Gate every release

1. Copy `scripts/scan_dist.py` into the repo, and `assets/gitleaks.toml` to `.gitleaks.toml` if there are
   reviewed false positives. Read any existing `.gitleaks.toml` first and merge; don't overwrite it.
2. Add a Makefile target: `scan: build` then `python scripts/scan_dist.py --dist dist --out scan-report`.
   Ignore `scan-report/` in git.
3. Paste `assets/dist-scan-job.yml` into the release workflow and add `dist-scan` to the publish job's `needs:`.
   Tools are pinned there: gitleaks by version and SHA-256, the Python tools with `uv tool install X==ver`. Lint
   the workflow with `actionlint` and `zizmor`.
4. Write a "reviewed heuristic hits" list in the release guide, so a reviewer can match the firewall's report
   line by line.
5. Expect new advisories on release day. Trivy or pip-audit may block a tag over a CVE published hours earlier.
   Bump the lockfile, and release the next version rather than re-tagging one that already reached TestPyPI.

## Free tools

| Need | Tools |
| --- | --- |
| Dependency CVEs | pip-audit, osv-scanner, Grype + Syft, Trivy, OWASP Dependency-Check; Dependabot (free on public repos) |
| Secrets | gitleaks, trufflehog, detect-secrets; GitHub secret scanning (public repos) |
| Malicious-package heuristics | GuardDog; Socket.dev public package pages (open in a browser) |
| Code issues | Bandit, Semgrep CE, CodeQL (public repos) |
| Licences | ScanCode Toolkit (closest to Black Duck's licence scan), Trivy, `reuse lint` |
| SBOM and posture | Syft or CycloneDX SBOMs, OpenSSF Scorecard, build provenance attestations |

More detail on each reason and on reading Black Duck output: [references/quarantine-reasons.md](references/quarantine-reasons.md).
