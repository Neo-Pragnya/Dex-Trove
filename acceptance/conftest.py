"""Dex Trove acceptance suite: shared harness steps plus Dex-specific fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

# Works under any pytest import mode (Dex uses importlib, which does not put this folder on sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent))

import re
import shutil
import subprocess

from harness import *  # noqa: F403  (steps, sandbox fixture and the release-gate hooks)
from harness import FIXTURES, REPO, Sandbox, fake_credential
from pytest_bdd import given, then

collect_ignore = ["fixtures", "site"]


def _package_version() -> str:
    text = (REPO / "src" / "dex_trove" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    assert match, "no __version__"
    return match.group(1)


@then("the output names the package version")
def output_has_version(sandbox: Sandbox) -> None:
    assert _package_version() in sandbox.last.stdout, sandbox.last.describe()


SOURCES = """\
sources:
  - id: good
    title: Good upstream
    adapter: agent-skills
    local: upstreams/good-up
    license: { expected: MIT }
  - id: mixed
    title: Mixed upstream
    adapter: agent-skills
    local: upstreams/mixed-up
"""


def _git_commit_all(path, env) -> None:  # type: ignore[no-untyped-def]
    for args in (
        ["init", "-q", "-b", "main"],
        ["add", "-A"],
        ["-c", "commit.gpgsign=false", "commit", "-qm", "fixture"],
    ):
        subprocess.run(["git", *args], cwd=path, env=env, capture_output=True, check=True)


@given("a maintainer checkout learning the fixture upstreams")
def maintainer_checkout(sandbox: Sandbox) -> None:
    """A Dex-Trove-shaped checkout (sources.yaml + src/dex_trove/) whose two sources are local fixture repos.

    good:  MIT at the root; csv-summary, release-notes (ships a script); private-notes hidden by .dexignore.
    mixed: no root licence; Apache via frontmatter; proprietary, unlicensed and bundled-GPL items; an exact
           duplicate of good/csv-summary; plus, generated here so nothing secret-shaped or huge is committed,
           a skill with a real-format AWS key and one with a 6 MB file.
    """
    root = sandbox.project
    shutil.copytree(FIXTURES / "upstreams", root / "upstreams")
    leaky = root / "upstreams" / "mixed-up" / "skills" / "leaky-skill"
    leaky.mkdir(parents=True)
    (leaky / "SKILL.md").write_text(
        "---\nname: leaky-skill\ndescription: Calls AWS.\nlicense: MIT\n---\n\n"
        f"export AWS_ACCESS_KEY_ID={fake_credential('aws-access-key')}\n",
        encoding="utf-8",
    )
    big = root / "upstreams" / "mixed-up" / "skills" / "big-skill"
    big.mkdir(parents=True)
    (big / "SKILL.md").write_text(
        "---\nname: big-skill\ndescription: Ships a huge asset.\nlicense: MIT\n---\n", encoding="utf-8"
    )
    (big / "data.bin").write_bytes(b"0" * 6_000_000)
    env = sandbox.env()
    for upstream in ("good-up", "mixed-up"):
        _git_commit_all(root / "upstreams" / upstream, env)
    (root / "sources.yaml").write_text(SOURCES, encoding="utf-8")
    (root / "src" / "dex_trove").mkdir(parents=True)
    (root / "src" / "dex_trove" / ".keep").write_text("", encoding="utf-8")
    (root / ".gitignore").write_text("upstreams/\n", encoding="utf-8")
    _git_commit_all(root, env)
