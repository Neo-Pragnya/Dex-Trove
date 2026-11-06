#!/usr/bin/env python3
"""Harvest a reusable project scaffold from an existing repository, safely.

  harvest.py detect path/to/repo                       # layout + technologies; copies nothing
  harvest.py template path/to/repo -o tpl --name acme-api [--version 1.0.0] [--test "python -m pytest -q"]
  harvest.py render tpl -o new-project --set project_name=billing-api
  harvest.py test tpl --set project_name=demo          # render into a scratch folder and run the template's test

`template` copies only structural files (build and tool configs, CI workflows, ignore files, a README skeleton)
plus the folder layout, never application code. It replaces the project's name with variables, and refuses:
secret-shaped text, `.env` files, files marked proprietary or confidential, and repositories whose licence isn't
permissive (pass --own when you own the code). Nothing is published: see SKILL.md for the reviewed path into Dex.
Python 3.9+, standard library only.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCHEMA = "scaffold-harvesting/template@1"
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".mypy_cache", ".pytest_cache", ".ruff_cache", "site-packages", ".next", "coverage"}
STRUCTURAL = [
    "pyproject.toml", "setup.cfg", "requirements*.txt", "package.json", "tsconfig*.json", "go.mod", "Cargo.toml",
    "Makefile", "Dockerfile", "docker-compose.y*ml", "compose.y*ml", ".gitignore", ".dockerignore", ".editorconfig",
    ".pre-commit-config.yaml", "ruff.toml", ".eslintrc*", "eslint.config.*", ".prettierrc*", "vite.config.*",
    "vitest.config.*", "jest.config.*", "pytest.ini", "tox.ini", ".github/workflows/*.yml", ".github/workflows/*.yaml",
    ".github/dependabot.yml", "README.md",
]
FRAMEWORKS = {
    "fastapi": "FastAPI", "django": "Django", "flask": "Flask", "pytest": "pytest", "typer": "Typer", "pydantic": "Pydantic",
    "express": "Express", "fastify": "Fastify", "react": "React", "next": "Next.js", "vue": "Vue", "astro": "Astro",
    "vitest": "Vitest", "jest": "Jest", "playwright": "Playwright", "@playwright/test": "Playwright", "typescript": "TypeScript",
}
SECRET = re.compile(r"AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,}|sk_live_[A-Za-z0-9]{16,}"
                    r"|(?i:(?:password|secret|token|api[_-]?key)\s*[:=]\s*['\"][^'\"\s$]{8,}['\"])")  # `$VAR`/`${{ }}` are references, not secrets
PROPRIETARY = re.compile(r"(?i)\b(?:all rights reserved|proprietary|confidential|do not distribute)\b")
PERMISSIVE = {"MIT": r"Permission is hereby granted, free of charge", "Apache-2.0": r"Apache License\s+Version 2\.0",
              "BSD": r"Redistribution and use in source and binary forms", "ISC": r"Permission to use, copy, modify, and/or distribute",
              "Unlicense": r"This is free and unencumbered software"}


class HarvestError(Exception):
    pass


def ignored_dirs(root: Path) -> set[str]:
    """Top-level folder names the repository's own .gitignore excludes (generated output, caches)."""
    f = root / ".gitignore"
    if not f.is_file():
        return set()
    names = set()
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        name = line.strip("/")
        # only whole top-level folders: "dist/", "/scan-report"; nested paths like "a/report/" leave "a" alone
        if name and not line.startswith(("#", "!")) and "/" not in name and not any(c in name for c in "*?["):
            names.add(name)
    return names


def walk(root: Path):
    skip = SKIP_DIRS | ignored_dirs(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in skip and not d.endswith(".egg-info"))
        for f in sorted(filenames):
            yield Path(dirpath) / f


def licence(root: Path) -> str:
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"):
        f = root / name
        if f.is_file():
            text = f.read_text(encoding="utf-8", errors="replace")
            return next((k for k, pat in PERMISSIVE.items() if re.search(pat, text)), "other")
    return "none"


def detect(root: Path) -> dict:
    if not root.is_dir():
        raise HarvestError(f"{root} is not a folder")
    files = [p.relative_to(root).as_posix() for p in walk(root)]
    tech: set[str] = set()
    for rel in files:
        name = rel.rsplit("/", 1)[-1]
        if name == "package.json":
            try:
                pkg = json.loads((root / rel).read_text(encoding="utf-8"))
            except ValueError:
                continue
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            tech |= {FRAMEWORKS[d] for d in deps if d in FRAMEWORKS} | {"Node.js"}
        elif name in ("pyproject.toml", "requirements.txt"):
            text = (root / rel).read_text(encoding="utf-8", errors="replace").lower()
            tech |= {v for k, v in FRAMEWORKS.items() if re.search(rf"(?m)^\s*[\"']?{re.escape(k)}\b", text) or f'"{k}' in text}
            tech.add("Python")
        elif name == "Dockerfile":
            tech.add("Docker")
        elif name in ("go.mod", "Cargo.toml"):
            tech.add("Go" if name == "go.mod" else "Rust")
    if any(f.startswith(".github/workflows/") for f in files):
        tech.add("GitHub Actions")
    top = sorted({f.split("/", 1)[0] for f in files if "/" in f})
    structural = [f for f in files if any(fnmatch.fnmatch(f, pat) for pat in STRUCTURAL)]
    return {"root": root.name, "licence": licence(root), "technologies": sorted(tech), "top_level_dirs": top,
            "structural_files": structural, "file_count": len(files)}


def variants(name: str) -> list[tuple[str, str]]:
    words = re.split(r"[-_ ]+", name.strip())
    if not words or not words[0]:
        raise HarvestError("--name must be the project's current name, e.g. acme-api")
    kebab, snake = "-".join(w.lower() for w in words), "_".join(w.lower() for w in words)
    title = " ".join(w.capitalize() for w in words)
    pascal = "".join(w.capitalize() for w in words)
    # longest first, so "acme_api" isn't half-replaced by a shorter variant
    pairs = [(title, "{{project_title}}"), (pascal, "{{project_class}}"), (kebab, "{{project_name}}"), (snake, "{{package_name}}")]
    return sorted(dict(pairs).items(), key=lambda kv: -len(kv[0]))


def cmd_template(a: argparse.Namespace) -> None:
    root = Path(a.repo).resolve()
    info = detect(root)
    if info["licence"] not in PERMISSIVE and not a.own:
        raise HarvestError(f"licence is {info['licence']!r}: only permissively licensed code may be harvested; pass --own if you own it")
    out = Path(a.output)
    if out.exists() and any(out.iterdir()):
        raise HarvestError(f"{out} isn't empty")
    problems, kept, skipped = [], [], []
    for rel in info["structural_files"]:
        f = root / rel
        if f.name.startswith(".env"):
            skipped.append(f"{rel}: environment file")
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        if SECRET.search(text):
            problems.append(f"{rel}: secret-shaped text")
            continue
        if PROPRIETARY.search(text):
            skipped.append(f"{rel}: marked proprietary or confidential")
            continue
        if rel == "README.md":
            text = f"# {a.name}\n\nDescribe {{{{project_title}}}} here.\n"
        for old, new in variants(a.name):
            text = text.replace(old, new)
        dest = out / "files" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        kept.append(rel)
    if problems:
        shutil.rmtree(out, ignore_errors=True)
        raise HarvestError("refused, nothing written: " + "; ".join(problems))
    for d in info["top_level_dirs"]:
        if not d.startswith("."):
            keep = out / "files" / d / ".gitkeep"
            keep.parent.mkdir(parents=True, exist_ok=True)
            keep.touch()
    manifest = {"schema": SCHEMA, "name": a.name, "version": a.version, "source_licence": info["licence"],
                "technologies": info["technologies"], "variables": ["project_name", "package_name", "project_title", "project_class"],
                "files": kept, "skipped": skipped, "test": a.test or ""}
    (out / "template.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"template {a.name}@{a.version}: {len(kept)} files, {len(skipped)} skipped → {out}")
    for s in skipped:
        print(f"  skipped {s}")


def _values(sets: list[str]) -> dict[str, str]:
    vals = dict(s.split("=", 1) for s in sets or [])
    if "project_name" not in vals:
        raise HarvestError("pass --set project_name=<kebab-name>")
    words = re.split(r"[-_ ]+", vals["project_name"])
    vals.setdefault("package_name", "_".join(w.lower() for w in words))
    vals.setdefault("project_title", " ".join(w.capitalize() for w in words))
    vals.setdefault("project_class", "".join(w.capitalize() for w in words))
    return vals


def render(tpl: Path, out: Path, vals: dict[str, str]) -> dict:
    m = json.loads((tpl / "template.json").read_text(encoding="utf-8"))
    if m.get("schema") != SCHEMA:
        raise HarvestError(f"{tpl} is not a harvested template")
    for f in sorted((tpl / "files").rglob("*")):
        if f.is_file():
            rel = f.relative_to(tpl / "files").as_posix()
            text = f.read_text(encoding="utf-8")
            for k, v in vals.items():
                text = text.replace("{{" + k + "}}", v)
            left = re.findall(r"\{\{(\w+)\}\}", text)
            if left:
                raise HarvestError(f"{rel}: no value for {', '.join(sorted(set(left)))}")
            dest = out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
    return m


def cmd_render(a: argparse.Namespace) -> None:
    out = Path(a.output)
    if out.exists() and any(out.iterdir()):
        raise HarvestError(f"{out} isn't empty")
    m = render(Path(a.template), out, _values(a.set))
    print(f"rendered {m['name']}@{m['version']} → {out}")


def cmd_test(a: argparse.Namespace) -> int:
    tpl = Path(a.template)
    with tempfile.TemporaryDirectory(prefix="scaffold-test-") as tmp:
        m = render(tpl, Path(tmp), _values(a.set))
        cmd = a.command or m.get("test")
        if not cmd:
            print("rendered cleanly; the template declares no test command")
            return 0
        env = {"PATH": os.environ.get("PATH", ""), "HOME": tmp, "LANG": "C.UTF-8"}  # no inherited secrets
        res = subprocess.run(cmd, shell=True, cwd=tmp, env=env, timeout=a.timeout)  # noqa: S602 - the template's declared test, run in a temp copy with no inherited secrets  # nosec B602
        print(f"test {'passed' if res.returncode == 0 else 'failed'}: {cmd}")
        return 0 if res.returncode == 0 else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("detect"); x.add_argument("repo")
    x = sub.add_parser("template"); x.add_argument("repo"); x.add_argument("-o", "--output", required=True); x.add_argument("--name", required=True)
    x.add_argument("--version", default="1.0.0"); x.add_argument("--test"); x.add_argument("--own", action="store_true")
    x = sub.add_parser("render"); x.add_argument("template"); x.add_argument("-o", "--output", required=True); x.add_argument("--set", action="append")
    x = sub.add_parser("test"); x.add_argument("template"); x.add_argument("--set", action="append"); x.add_argument("--command"); x.add_argument("--timeout", type=int, default=600)
    a = p.parse_args(argv)
    try:
        if a.cmd == "detect":
            print(json.dumps(detect(Path(a.repo).resolve()), indent=2))
            return 0
        rc = globals()[f"cmd_{a.cmd}"](a)
    except (HarvestError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return rc or 0


if __name__ == "__main__":
    sys.exit(main())
