.PHONY: install lint format format-check typecheck test coverage verify validate learn notices \
        build build-check sbom trivy-scan trivy-scan-json trivy-scan-sarif security \
        docs-export docs-install docs-build docs-serve publish-testpypi publish-pypi clean check-uv \
        acceptance acceptance-wheel acceptance-dist acceptance-site

UV := uv
# Load local publish tokens (UV_PUBLISH_TOKEN, UV_PUBLISH_TOKEN_TESTPYPI) when present. Never committed.
-include .env
export

# ── Setup ──────────────────────────────────────────────────────────────────
check-uv:
	@command -v $(UV) >/dev/null 2>&1 || \
	  (echo "uv not found — install: curl -LsSf https://astral.sh/uv/install.sh | sh" && exit 1)

install: check-uv
	$(UV) sync --all-extras

# ── Quality ────────────────────────────────────────────────────────────────
lint:
	$(UV) run ruff check src tests hatch_build.py

format:
	$(UV) run ruff format src tests hatch_build.py

format-check:
	$(UV) run ruff format --check src tests hatch_build.py

typecheck:
	$(UV) run mypy src

test:
	$(UV) run pytest

coverage:
	$(UV) run pytest --cov=src/dex_trove --cov-report=html --cov-report=term
	@echo "HTML report: htmlcov $(ACCEPTANCE_VENV) acceptance/report/index.html"

validate:
	$(UV) run dex validate

verify: lint format-check typecheck test validate

# ── Trove ──────────────────────────────────────────────────────────────────
learn:
	$(UV) run dex learn

notices:
	$(UV) run dex notices

# ── Security ───────────────────────────────────────────────────────────────
# The blocking gate covers the package and its dependencies. trove/ is upstream *content* (it may contain
# example lockfiles or placeholder credentials) and is scanned separately, non-blocking — see SECURITY.md.
TRIVY_GATE := --skip-dirs trove --skip-dirs website/node_modules --ignorefile .trivyignore --ignore-unfixed

trivy-scan:
	@command -v trivy >/dev/null 2>&1 || \
	  (echo "trivy not found — https://aquasecurity.github.io/trivy/latest/getting-started/installation/" && exit 1)
	trivy fs . $(TRIVY_GATE) --exit-code 1 --severity CRITICAL,HIGH --format table
	@echo "Trivy scan passed."

trivy-scan-json:
	@command -v trivy >/dev/null 2>&1 || (echo "trivy not found" && exit 1)
	trivy fs . $(TRIVY_GATE) --format json --output trivy-report.json --severity CRITICAL,HIGH,MEDIUM

trivy-scan-sarif:
	@command -v trivy >/dev/null 2>&1 || (echo "trivy not found" && exit 1)
	trivy fs . $(TRIVY_GATE) --format sarif --output trivy-results.sarif --severity CRITICAL,HIGH

security: trivy-scan
	$(UV) run --with pip-audit pip-audit
	@echo "Security scans complete."

# ── Build ──────────────────────────────────────────────────────────────────
build: check-uv
	rm -rf dist
	$(UV) build
	@echo "Artifacts in dist/:"
	@ls -lh dist/

build-check: build
	$(UV) run --with twine twine check dist/*

sbom:
	$(UV) run --with cyclonedx-bom cyclonedx-py environment \
	  --output-format json \
	  --output-file dist/sbom.cdx.json
	@echo "SBOM written to dist/sbom.cdx.json"

# ── Docs site (Astro) ──────────────────────────────────────────────────────
docs-export:
	$(UV) run dex docs export --out website/src

docs-install:
	cd website && npm ci

docs-build: docs-export
	cd website && npm run build

docs-serve: docs-export
	cd website && npm run dev

# ── Publish ────────────────────────────────────────────────────────────────
# Set UV_PUBLISH_TOKEN / UV_PUBLISH_TOKEN_TESTPYPI in .env (see .env.example). CI uses OIDC instead.
publish-testpypi: verify build-check
	@echo "Publishing to TestPyPI via uv..."
	$(UV) publish \
	  --publish-url https://test.pypi.org/legacy/ \
	  --token "$$UV_PUBLISH_TOKEN_TESTPYPI"

publish-pypi: verify build-check
	@echo "Publishing to PyPI via uv..."
	$(UV) publish --token "$$UV_PUBLISH_TOKEN"

# ── Clean ──────────────────────────────────────────────────────────────────

# ── Acceptance (capability scenarios + release gate) ─────────────────────────
# Gherkin scenarios in acceptance/features drive the real CLI in sandboxes; the gate writes
# acceptance/report/{acceptance.json,summary.md} and fails on BLOCK. See acceptance/README.md.
ACCEPTANCE_VENV := .acceptance-venv
ACCEPTANCE_ARGS ?=

acceptance:
	$(UV) run --frozen pytest acceptance -n auto -p no:cacheprovider $(ACCEPTANCE_ARGS)

# What ships: build the wheel, install it (with the ananke extra) into a fresh venv, run the suite from there.
acceptance-wheel: build acceptance-dist

# Run against an already-built dist/*.whl (CI tests the exact artifact it publishes).
acceptance-dist:
	rm -rf $(ACCEPTANCE_VENV)
	$(UV) venv -q --python 3.12 $(ACCEPTANCE_VENV)
	$(UV) pip install -q --python $(ACCEPTANCE_VENV)/bin/python "$$(ls dist/*.whl | head -1)[ananke]" \
	  pytest pytest-bdd pytest-xdist pyyaml
	ACCEPTANCE_BIN_DIR=$(CURDIR)/$(ACCEPTANCE_VENV)/bin $(ACCEPTANCE_VENV)/bin/python -m pytest acceptance \
	  -n auto -p no:cacheprovider $(ACCEPTANCE_ARGS)

# Browser journeys on the built website (real Chrome, run serially: they are timing-sensitive under load).
acceptance-site:
	ACCEPTANCE_SITE_DIST=$(CURDIR)/website/dist $(UV) run --frozen pytest acceptance -p no:cacheprovider -k "site or journeys" \
	  $(ACCEPTANCE_ARGS)

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache htmlcov \
	       trivy-report.json trivy-results.sarif website/dist
