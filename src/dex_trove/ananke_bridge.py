"""Register trove items into an Ananke registry (DESIGN.md §9).

Uses the ``ananke`` CLI as the contract: Dex never writes Ananke's registry directly.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from dex_trove import catalog
from dex_trove.paths import trove_root


class AnankeError(RuntimeError):
    pass


def find_ananke(explicit: str | None = None) -> str:
    """``--ananke-bin``, else ``ananke`` on PATH, else the one beside this interpreter (an unactivated venv)."""
    exe = explicit or shutil.which("ananke")
    if not exe:
        sibling = Path(sys.executable).parent / ("ananke.exe" if os.name == "nt" else "ananke")
        exe = str(sibling) if sibling.is_file() else None
    if not exe:
        raise AnankeError("`ananke` not found on PATH — pip install ananke-plexus (or pass --ananke-bin)")
    return exe


def sync(
    *,
    project: Path,
    kinds: list[str] | None = None,
    sources: list[str] | None = None,
    names: list[str] | None = None,
    dry_run: bool = False,
    include_flagged: bool = False,
    ananke_bin: str | None = None,
    extra_args: list[str] | None = None,
) -> tuple[list[dict[str, Any]], subprocess.CompletedProcess[str]]:
    """``ananke registry learn`` over the selected items. Unfiltered syncs learn the trove root in place.

    Items carrying ``secret_flags`` (placeholders that Ananke's scanner refuses) are skipped unless
    ``include_flagged`` — then the project's Ananke policy (``[secrets] mode``) decides.
    """
    exe = find_ananke(ananke_bin)
    items = catalog.load()
    selected = [
        i
        for i in items
        if (not kinds or i["kind"] in kinds)
        and (not sources or i["namespace"] in sources)
        and (not names or i["name"] in names or i["id"] in names)
        and (include_flagged or not i.get("secret_flags"))
    ]
    if not selected:
        raise AnankeError("no trove items match the filters")
    cmd = [exe, "registry", "learn"]
    with tempfile.TemporaryDirectory(prefix="dex-ananke-") as tmp:
        if len(selected) == len(items):
            target = trove_root()
        else:
            target = Path(tmp) / "trove"
            for it in selected:
                shutil.copytree(catalog.item_path(it), target / it["dir"])
        cmd += [str(target), "--project", str(project)]
        if dry_run:
            cmd.append("--dry-run")
        cmd += extra_args or []
        proc = subprocess.run(cmd, capture_output=True, text=True)
    return selected, proc
