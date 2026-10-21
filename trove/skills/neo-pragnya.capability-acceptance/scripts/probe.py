#!/usr/bin/env python3
"""probe.py — learn what a CLI really does before you write an assertion about it.

    python probe.py --bin .venv/bin --project /tmp/probe commands.txt
    python probe.py --bin .venv/bin --fixture acceptance/fixtures/projects/shop commands.txt

Each non-empty, non-# line of commands.txt is a shell command, run in order (state carries over) in a sandbox
project with its own HOME, no colour and wide columns, the target's bin dir first on PATH. Prints the condensed
output and exit code of each. Read the results critically: anything that crashes, prints a success mark on a
failure, exits 0 after refusing, or changes on a second identical run is a finding, not a value to snapshot.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BOX = re.compile(r"^[\s┏┡└┃┳╇┩┓┻┛━─│╭╮╰╯]*$")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("commands", type=Path)
    ap.add_argument("--bin", type=Path, default=Path(sys.executable).parent, help="target bin dir (first on PATH)")
    ap.add_argument("--project", type=Path, help="project dir (default: a fresh temp dir)")
    ap.add_argument("--fixture", type=Path, help="copy this folder into the project and git-commit it first")
    ap.add_argument("--chars", type=int, default=700, help="max output characters shown per command")
    args = ap.parse_args()

    project = args.project or Path(tempfile.mkdtemp(prefix="probe-"))
    project.mkdir(parents=True, exist_ok=True)
    home = project.parent / (project.name + "-home")
    home.mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("VIRTUAL_ENV")}
    env.update(
        HOME=str(home), NO_COLOR="1", TERM="dumb", COLUMNS="200", PYTHONUTF8="1",
        PATH=f"{args.bin.resolve()}{os.pathsep}{os.environ.get('PATH', '')}",
        GIT_AUTHOR_NAME="probe", GIT_AUTHOR_EMAIL="probe@example.invalid",
        GIT_COMMITTER_NAME="probe", GIT_COMMITTER_EMAIL="probe@example.invalid",
    )
    if args.fixture:
        shutil.copytree(args.fixture, project, dirs_exist_ok=True)
        for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-qm", "fixture"]):
            subprocess.run(cmd, cwd=project, env=env, capture_output=True, check=False)
    print(f"# project: {project}\n# home:    {home}\n")
    for line in args.commands.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            proc = subprocess.run(
                ["bash", "-c", line], cwd=project, env=env, capture_output=True, text=True, errors="replace", timeout=600
            )
            out, code = proc.stdout + proc.stderr, proc.returncode
        except subprocess.TimeoutExpired:
            out, code = "TIMEOUT", -9
        kept = "\n".join(ln for ln in out.splitlines() if not BOX.match(ln))
        flags = []
        if "Traceback (most recent call last)" in out:
            flags.append("CRASH")
        first = next((ln.strip() for ln in out.splitlines() if ln.strip()), "")
        if code != 0 and first.startswith("✓"):
            flags.append("SUCCESS-MARK-ON-FAILURE")
        print(f"=== {line}\n{kept[: args.chars].rstrip()}\n[exit {code}]{'  ⚑ ' + ', '.join(flags) if flags else ''}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
