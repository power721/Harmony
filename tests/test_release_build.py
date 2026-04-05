"""Regression tests for release packaging configuration."""

from pathlib import Path
import re
import types

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


def test_find_libmpv_on_windows_resolves_chocolatey_layout(tmp_path, monkeypatch):
    """Windows MPV bundles should find mpv-2.dll in the Chocolatey install tree."""
    choco_root = tmp_path / "ProgramData" / "chocolatey"
    shim_dir = choco_root / "bin"
    runtime_dir = choco_root / "lib" / "mpv" / "tools" / "mpv"
    shim_dir.mkdir(parents=True)
    runtime_dir.mkdir(parents=True)

    (shim_dir / "mpv.exe").write_text("", encoding="utf-8")
    mpv_dll = runtime_dir / "mpv-2.dll"
    mpv_dll.write_text("", encoding="utf-8")

    monkeypatch.setattr(build.platform, "system", lambda: "Windows")
    monkeypatch.setattr(build, "PROJECT_ROOT", tmp_path / "repo")
    monkeypatch.setattr(build, "sys", types.SimpleNamespace(executable=str(tmp_path / "Python" / "python.exe")))
    monkeypatch.setattr(build.shutil, "which", lambda name: str(shim_dir / "mpv.exe") if name == "mpv" else None)
    monkeypatch.setenv("PATH", str(shim_dir))

    assert build.find_libmpv(build.AUDIO_BACKEND_MPV) == [(str(mpv_dll), ".")]


def test_find_libmpv_on_windows_resolves_chocolatey_package_variant(tmp_path, monkeypatch):
    """Windows MPV bundles should tolerate Chocolatey package names like mpvio.install."""
    choco_root = tmp_path / "ProgramData" / "chocolatey"
    shim_dir = choco_root / "bin"
    package_dir = choco_root / "lib" / "mpvio.install" / "tools"
    shim_dir.mkdir(parents=True)
    package_dir.mkdir(parents=True)

    (shim_dir / "mpv.exe").write_text("", encoding="utf-8")
    mpv_dll = package_dir / "mpv-2.dll"
    mpv_dll.write_text("", encoding="utf-8")

    monkeypatch.setattr(build.platform, "system", lambda: "Windows")
    monkeypatch.setattr(build, "PROJECT_ROOT", tmp_path / "repo")
    monkeypatch.setattr(build, "sys", types.SimpleNamespace(executable=str(tmp_path / "Python" / "python.exe")))
    monkeypatch.setattr(build.shutil, "which", lambda name: str(shim_dir / "mpv.exe") if name == "mpv" else None)
    monkeypatch.setenv("PATH", str(shim_dir))
    monkeypatch.setenv("ChocolateyInstall", str(choco_root))

    assert build.find_libmpv(build.AUDIO_BACKEND_MPV) == [(str(mpv_dll), ".")]


def test_windows_workflow_exports_mpv_runtime_directory():
    """Windows CI should export the directory containing mpv-2.dll before invoking build.py."""
    repo_root = Path(__file__).resolve().parents[1]
    content = (repo_root / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")

    build_windows_section = re.search(
        r"build-windows:\n(?P<section>.*?)(?:\n  release:|\Z)",
        content,
        re.DOTALL,
    )
    assert build_windows_section, "build.yml must define a build-windows job"

    section = build_windows_section.group("section")
    assert "mpv-2.dll" in section
    assert "$env:GITHUB_PATH" in section
    assert "$env:ChocolateyInstall" in section
