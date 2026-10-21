#!/usr/bin/env python3
"""scaffold_acceptance.py — give a repo a capability acceptance suite and release gate.

    python scaffold_acceptance.py <repo> --product "My Tool" --bin mytool [--bin mytool-admin] \
        [--version-file src/mytool/__init__.py] [--fixture-name sample] [--makefile] [--workflow] [--force]

Writes <repo>/acceptance/:
    harness.py           the shared harness (sandbox, Gherkin steps, PROMOTE / CONDITIONAL / BLOCK gate)
    capabilities.yaml    capability catalog (fill in) + the CLI surface, discovered from `<bin> --help`
    conftest.py          imports the harness; add repo-specific steps here
    test_acceptance.py   collects features/*.feature
    features/00_smoke.feature  a first scenario per binary (version + help) to grow from
    fixtures/projects/<fixture-name>/  a sample project for "Given a fresh project"
    README.md            how to run, add scenarios and read the gate
Optionally appends Makefile targets (acceptance, acceptance-wheel, acceptance-dist) and writes
.github/workflows/acceptance.yml. Needs pytest, pytest-bdd and PyYAML in the repo's dev environment.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
CMD_LINE = re.compile(r"^\s*(?:│\s*)?([a-z][a-z0-9-]*)\s{2,}\S")


def _help(argv: list[str]) -> str:
    env = {"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200", "PATH": __import__("os").environ.get("PATH", "")}
    try:
        p = subprocess.run([*argv, "--help"], capture_output=True, text=True, timeout=30, env=env, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return p.stdout + p.stderr


def discover(argv: list[str], depth: int = 3) -> list[str]:
    """Leaf commands under `argv`, read from the Commands section of --help (Typer/Rich or Click layout)."""
    text = _help(argv)
    section = re.split(r"\n\s*(?:╭─\s*)?Commands\b.*\n", text, maxsplit=1)
    if len(section) < 2:
        return [" ".join([Path(argv[0]).name, *argv[1:]])]
    names = []
    for line in section[1].splitlines():
        if re.match(r"^\s*(?:╰|$)", line) and names:
            break
        m = CMD_LINE.match(line)
        if m and m.group(1) not in ("help",):
            names.append(m.group(1))
    if not names or depth == 0:
        return [" ".join([Path(argv[0]).name, *argv[1:]])]
    out: list[str] = []
    for name in dict.fromkeys(names):
        out += discover([*argv, name], depth - 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", type=Path)
    ap.add_argument("--product", required=True)
    ap.add_argument("--bin", action="append", required=True, help="CLI binaries under test (repeatable)")
    ap.add_argument("--bin-dir", type=Path, help="where the binaries live for discovery (default: PATH)")
    ap.add_argument("--version-file", help="file holding __version__, for the version scenario")
    ap.add_argument("--fixture-name", default="sample")
    ap.add_argument("--makefile", action="store_true", help="append acceptance targets to the Makefile")
    ap.add_argument("--workflow", action="store_true", help="write .github/workflows/acceptance.yml")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    repo = args.repo.resolve()
    acc = repo / "acceptance"
    if acc.exists() and not args.force:
        print(f"{acc} exists (use --force to overwrite the scaffold files)", file=sys.stderr)
        return 1
    (acc / "features").mkdir(parents=True, exist_ok=True)
    (acc / "fixtures" / "projects" / args.fixture_name).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ASSETS / "harness.py", acc / "harness.py")

    surface: list[str] = []
    for b in args.bin:
        exe = str(args.bin_dir / b) if args.bin_dir else (shutil.which(b) or b)
        found = discover([exe])
        surface += [" ".join([b, *c.split()[1:]]) for c in found]
    print(f"discovered {len(surface)} commands")

    t = (ASSETS / "templates")
    (acc / "capabilities.yaml").write_text(
        (t / "capabilities.yaml").read_text()
        .replace("__PRODUCT__", args.product)
        .replace("__FIXTURE__", args.fixture_name)
        .replace("__BINARIES__", ", ".join(args.bin))
        .replace("__SURFACE__", "\n".join(f"  - {c}" for c in sorted(dict.fromkeys(surface))) or "  []"),
        encoding="utf-8",
    )
    version_file = args.version_file or ""
    (acc / "conftest.py").write_text(t.joinpath("conftest.py").read_text().replace("__VERSION_FILE__", version_file), encoding="utf-8")
    shutil.copyfile(t / "test_acceptance.py", acc / "test_acceptance.py")
    smoke = ["@cap_packaging", "Feature: The package installs cleanly", ""]
    for b in args.bin:
        smoke += [f"  Scenario: {b} starts and lists its commands", f'    When I run "{b} --help"', "    Then it succeeds",
                  "    And it finishes within 6 seconds", ""]
    if version_file:
        smoke += ["  Scenario: The CLI reports the version being released", f'    When I run "{args.bin[0]} --version"',
                  "    Then it succeeds", "    And the output names the package version", ""]
    (acc / "features" / "00_smoke.feature").write_text("\n".join(smoke), encoding="utf-8")
    (acc / "fixtures" / "projects" / args.fixture_name / "README.md").write_text(
        f"# {args.fixture_name}\n\nSample project used by `Given a fresh project`. Make it look like a real user's repo.\n",
        encoding="utf-8",
    )
    (acc / "README.md").write_text(t.joinpath("README.md").read_text().replace("__PRODUCT__", args.product), encoding="utf-8")

    gi = repo / ".gitignore"
    lines = gi.read_text().splitlines() if gi.exists() else []
    add = [x for x in (".acceptance-venv/", "acceptance/report/") if x not in lines]
    if add:
        gi.write_text("\n".join([*lines, "", "# acceptance suite", *add]) + "\n", encoding="utf-8")
    if args.makefile:
        mk = repo / "Makefile"
        snippet = (t / "Makefile.snippet").read_text()
        if "acceptance-wheel" not in (mk.read_text() if mk.exists() else ""):
            with mk.open("a", encoding="utf-8") as fh:
                fh.write("\n" + snippet)
            print("appended acceptance targets to Makefile")
    if args.workflow:
        wf = repo / ".github" / "workflows" / "acceptance.yml"
        wf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(t / "acceptance.yml", wf)
        print(f"wrote {wf}")
    print(f"scaffolded {acc}. Next: list capabilities in capabilities.yaml, probe commands with scripts/probe.py,")
    print("write features/NN_<area>.feature tagged @cap_<id>, then: pytest acceptance -n auto")
    return 0


if __name__ == "__main__":
    sys.exit(main())
