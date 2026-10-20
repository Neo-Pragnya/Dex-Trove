"""Hatch build hook: ship trove/ inside the wheel as package data of ``dex_trove``."""

from __future__ import annotations

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

TROVE_FILES = ("catalog.json", "EXCLUDED.json", "trove.lock.json")


class TroveBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict) -> None:
        root = Path(self.root)
        trove = root / "trove"
        force = build_data.setdefault("force_include", {})
        if trove.is_dir():
            for child in sorted(trove.iterdir()):
                if child.is_dir() or child.name in TROVE_FILES:
                    force[str(child)] = f"dex_trove/{child.name}"
        sources = root / "sources.yaml"
        if sources.is_file():
            force[str(sources)] = "dex_trove/sources.yaml"
