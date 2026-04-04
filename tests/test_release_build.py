"""Regression tests for Linux release packaging."""

from pathlib import Path
import re


def test_release_script_includes_mpv_hidden_import():
    """Linux AppImage builds must bundle the python-mpv module."""
    repo_root = Path(__file__).resolve().parents[1]
    content = (repo_root / "release.sh").read_text(encoding="utf-8")

    assert re.search(r"--hidden-import\s+mpv\b", content), (
        "release.sh must pass --hidden-import mpv to PyInstaller so "
        "AppImage builds include the python-mpv module."
    )
