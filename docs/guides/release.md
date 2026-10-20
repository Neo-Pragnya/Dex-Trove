---
title: Release
description: How dex-trove is versioned, gated and published to TestPyPI and PyPI.
---

# Release guide

Dex Trove's release engineering mirrors [Ananke Plexus](https://github.com/Neo-Pragnya/Ananke-Plexus): **uv**
for everything, build once, Trivy gate, provenance attestation, and OIDC trusted publishing to TestPyPI and PyPI.

## Build tooling

| Action | Command |
| --- | --- |
| Install dev env | `make install` / `uv sync --all-extras` |
| Full quality gate | `make verify` (ruff, format, mypy strict, pytest, `dex validate`) |
| Build artifacts | `make build` / `uv build` |
| Validate metadata | `make build-check` / `uv run --with twine twine check dist/*` |
| Security scan | `make security` (Trivy + pip-audit) |
| Publish to TestPyPI | `make publish-testpypi` |
| Publish to PyPI | `make publish-pypi` |

## 1. One-time setup

1. On [PyPI](https://pypi.org/manage/account/publishing/) and [TestPyPI](https://test.pypi.org/manage/account/publishing/),
   add a **trusted publisher** (a "pending publisher" before the first upload):
   - **Project:** `dex-trove`
   - **Owner:** `Neo-Pragnya` · **Repository:** `Dex-Trove`
   - **Workflow:** `release-pypi.yml` (or `release-testpypi.yml` for TestPyPI)
   - **Environment:** `pypi` (or `testpypi`)
2. In the GitHub repo, create **environments** `pypi` and `testpypi` (Settings → Environments). Add required
   reviewers to `pypi`.
3. Enable **Pages** with source **GitHub Actions** for the docs site.

No long-lived PyPI tokens are stored in GitHub; OIDC handles authentication.

## 2. Prepare the release

```bash
make install
uv run dex learn                 # refresh the trove (or a single source)
make verify                      # must be green
make docs-build                  # site must build
```

Then:

1. Bump `__version__` in `src/dex_trove/__init__.py`.
2. Move `[Unreleased]` notes in `CHANGELOG.md` under the new version, including the trove summary (items per
   source, notable exclusions).
3. Commit, tag and push:

```bash
VERSION="$(uv run python -c 'from dex_trove import __version__; print(__version__)')"
git add src/dex_trove/__init__.py CHANGELOG.md trove THIRD_PARTY_NOTICES.md
git commit -m "chore: release v$VERSION"
git tag "v$VERSION"
git push origin main "v$VERSION"
```

## 3. What the tag triggers

```text
release-testpypi.yml            release-pypi.yml
  └─ build                        └─ build (version check · tests · dex validate · uv build · twine check · SBOM)
  └─ trivy (CRITICAL)             └─ trivy (CRITICAL + HIGH, blocking)
  └─ provenance                   └─ provenance (attest-build-provenance)
  └─ publish TestPyPI             └─ publish PyPI (OIDC, token fallback)
                                  └─ GitHub Release (dist + notes)
```

**Build once:** the publish job uploads exactly the files the build job produced and the gates checked.

**Idempotent:** if the version is already on (Test)PyPI, for example after a manual `make publish-pypi`, the
publish job is skipped and only the GitHub Release is created.

## 4. Manual publish (fallback)

Only needed when trusted publishing isn't configured yet:

```bash
cp .env.example .env    # set UV_PUBLISH_TOKEN and UV_PUBLISH_TOKEN_TESTPYPI
make publish-testpypi
uv tool install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ dex-trove
dex --version
make publish-pypi
```

Both targets run `make verify` and `twine check` first. `.env` is gitignored.

## 5. Post-release checks

```bash
uv tool install dex-trove          # or: pip install -U dex-trove
dex --version
dex search architecture
python -m venv /tmp/a && /tmp/a/bin/pip install dex-trove ananke-plexus
cd "$(mktemp -d)" && /tmp/a/bin/ananke registry init && /tmp/a/bin/dex ananke sync --source neo-pragnya
```

## Size budget

The 0.1.0 wheel is about 15 MB (sdist about 12 MB). PyPI's default file limit is 100 MB. CI prints the manifest
count on every run. If the trove outgrows the limit, split it into per-source extras (`dex-trove[anthropic]`).
