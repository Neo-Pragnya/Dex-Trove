"""Which trove the CLI operates on."""

from __future__ import annotations

from pathlib import Path

import pytest

from dex_trove import paths


def _fake_package(tmp_path: Path) -> Path:
    pkg = tmp_path / "site-packages" / "dex_trove"
    pkg.mkdir(parents=True)
    (pkg / "catalog.json").write_text("{}")
    return pkg


def test_inside_a_checkout_the_checkout_trove_wins_over_the_installed_wheel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DEX_TROVE_ROOT", raising=False)
    monkeypatch.setattr(paths, "PACKAGE_DIR", _fake_package(tmp_path))
    checkout = tmp_path / "checkout"
    (checkout / "src" / "dex_trove").mkdir(parents=True)
    (checkout / "sources.yaml").write_text("sources: []\n")
    (checkout / "sub").mkdir()
    monkeypatch.chdir(checkout / "sub")
    assert paths.trove_root() == (checkout / "trove").resolve()


def test_outside_a_checkout_the_installed_trove_is_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DEX_TROVE_ROOT", raising=False)
    pkg = _fake_package(tmp_path)
    monkeypatch.setattr(paths, "PACKAGE_DIR", pkg)
    (tmp_path / "elsewhere").mkdir()
    monkeypatch.chdir(tmp_path / "elsewhere")
    assert paths.trove_root() == pkg


def test_the_environment_variable_always_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEX_TROVE_ROOT", str(tmp_path / "custom"))
    assert paths.trove_root() == (tmp_path / "custom").resolve()
