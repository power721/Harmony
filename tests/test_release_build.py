"""Regression tests for release packaging configuration."""

from pathlib import Path
import re

import build


def test_release_script_includes_mpv_hidden_import():
    """Linux AppImage builds must bundle the python-mpv module."""
    repo_root = Path(__file__).resolve().parents[1]
    content = (repo_root / "release.sh").read_text(encoding="utf-8")

    assert re.search(r"--hidden-import\s+mpv\b", content), (
        "release.sh must pass --hidden-import mpv to PyInstaller so "
        "AppImage builds include the python-mpv module."
    )


def test_windows_mpv_bundle_excludes_qt_multimedia_plugins():
    """MPV-only Windows builds should not bundle Qt audio/multimedia plugins."""
    plugin_dirs = build.get_qt_plugin_dirs(build.AUDIO_BACKEND_MPV)

    assert "platforms" in plugin_dirs
    assert "imageformats" in plugin_dirs
    assert "multimedia" not in plugin_dirs
    assert "audio" not in plugin_dirs
    assert "mediaservice" not in plugin_dirs


def test_windows_workflow_produces_split_backend_executables():
    """Windows CI must upload separate QT and MPV executables without a portable zip."""
    repo_root = Path(__file__).resolve().parents[1]
    content = (repo_root / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")

    build_windows_section = re.search(
        r"build-windows:\n(?P<section>.*?)(?:\n  release:|\Z)",
        content,
        re.DOTALL,
    )
    assert build_windows_section, "build.yml must define a build-windows job"

    section = build_windows_section.group("section")
    assert "Harmony-${env:APP_VERSION}-windows-QT.exe" in section
    assert "Harmony-${env:APP_VERSION}-windows-MPV.exe" in section
    assert "Create portable zip" not in section
    assert 'dist/Harmony-${env:APP_VERSION}-windows.zip' not in section
