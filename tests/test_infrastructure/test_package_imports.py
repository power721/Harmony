"""Regression tests for package-level lazy imports in packaged builds."""

from __future__ import annotations

import importlib.abc
import importlib.util
import sys
from pathlib import Path


class _BlockMpvBackendFinder(importlib.abc.MetaPathFinder):
    def __init__(self, blocked_module: str):
        self._blocked_module = blocked_module

    def find_spec(self, fullname, path=None, target=None):
        if fullname == self._blocked_module:
            raise ModuleNotFoundError(f"No module named '{fullname}'")
        return None


def _load_package(package_name: str, package_dir: Path):
    init_file = package_dir / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        package_name,
        init_file,
        submodule_search_locations=[str(package_dir)],
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    try:
        spec.loader.exec_module(module)
        return module
    finally:
        sys.modules.pop(package_name, None)


def test_audio_package_import_succeeds_without_mpv_backend(monkeypatch):
    """QT-only bundles should import infrastructure.audio without mpv backend."""
    package_name = "tests_lazy_audio_pkg"
    package_dir = Path(__file__).resolve().parents[2] / "infrastructure" / "audio"
    monkeypatch.syspath_prepend(str(package_dir.parent.parent))
    monkeypatch.setattr(
        sys,
        "meta_path",
        [_BlockMpvBackendFinder(f"{package_name}.mpv_backend"), *sys.meta_path],
    )

    module = _load_package(package_name, package_dir)

    assert module.AudioBackend.__name__ == "AudioBackend"
    assert module.PlayerEngine.__name__ == "PlayerEngine"


def test_infrastructure_package_import_succeeds_without_mpv_backend(monkeypatch):
    """QT-only bundles should import infrastructure package without mpv backend."""
    package_name = "tests_lazy_infra_pkg"
    package_dir = Path(__file__).resolve().parents[2] / "infrastructure"
    monkeypatch.syspath_prepend(str(package_dir.parent))
    monkeypatch.setattr(
        sys,
        "meta_path",
        [_BlockMpvBackendFinder(f"{package_name}.audio.mpv_backend"), *sys.meta_path],
    )

    module = _load_package(package_name, package_dir)

    assert module.AudioBackend.__name__ == "AudioBackend"
    assert module.PlayerEngine.__name__ == "PlayerEngine"
