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
    assert "platforminputcontexts" in plugin_dirs
    assert "multimedia" not in plugin_dirs
    assert "audio" not in plugin_dirs
    assert "mediaservice" not in plugin_dirs


def test_release_script_safe_plugin_dirs_keep_platform_input_contexts():
    """Linux AppImage pruning must retain Qt input method plugins."""
    repo_root = Path(__file__).resolve().parents[1]
    content = (repo_root / "release.sh").read_text(encoding="utf-8")

    assert "SAFE_DIRS=(platforms imageformats iconengines platforminputcontexts" in content


def test_release_script_explicitly_collects_platform_input_context_plugins():
    """Linux CI build must copy Qt input method plugins into the PyInstaller bundle."""
    repo_root = Path(__file__).resolve().parents[1]
    content = (repo_root / "release.sh").read_text(encoding="utf-8")

    assert "collect_qt_input_context_plugins" in content
    assert 'platforminputcontexts' in content
    assert 'uv run python' in content


def test_release_script_bundles_builtin_plugins_for_linux_appimage():
    """Linux CI build must ship builtin plugins inside the PyInstaller bundle."""
    repo_root = Path(__file__).resolve().parents[1]
    content = (repo_root / "release.sh").read_text(encoding="utf-8")

    assert '--add-data "plugins/builtin:plugins/builtin"' in content


def test_release_script_collects_crypto_for_builtin_plugins():
    """Linux AppImage builds must bundle Crypto for dynamically loaded builtin plugins."""
    repo_root = Path(__file__).resolve().parents[1]
    content = (repo_root / "release.sh").read_text(encoding="utf-8")

    assert '--collect-all Crypto' in content, (
        "release.sh must collect the Crypto package because builtin plugins are "
        "copied as data and PyInstaller does not analyze their imports."
    )


def test_release_script_apprun_initializes_dbus_session():
    """Linux AppImage launcher should prepare a D-Bus session for MPRIS."""
    repo_root = Path(__file__).resolve().parents[1]
    content = (repo_root / "release.sh").read_text(encoding="utf-8")

    assert "DBUS_SESSION_BUS_ADDRESS" in content
    assert "dbus-launch --sh-syntax" in content
    assert 'local bus_path="/run/user/$uid/bus"' in content


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


def test_find_libmpv_on_windows_prefers_repo_download_dir(tmp_path, monkeypatch):
    """Windows MPV bundles should resolve a downloaded repo-local mpv runtime first."""
    repo_root = tmp_path / "repo"
    bundled_dir = repo_root / "mpv"
    bundled_dir.mkdir(parents=True)
    mpv_dll = bundled_dir / "libmpv-2.dll"
    mpv_dll.write_text("", encoding="utf-8")

    monkeypatch.setattr(build.platform, "system", lambda: "Windows")
    monkeypatch.setattr(build, "PROJECT_ROOT", repo_root)
    monkeypatch.setattr(build, "sys", types.SimpleNamespace(executable=str(tmp_path / "Python" / "python.exe")))
    monkeypatch.setenv("PATH", "")

    assert build.find_libmpv(build.AUDIO_BACKEND_MPV) == [(str(mpv_dll), ".")]


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


def test_windows_workflow_downloads_repo_mpv_runtime():
    """Windows CI should download libmpv into the repo instead of installing Chocolatey mpv."""
    repo_root = Path(__file__).resolve().parents[1]
    content = (repo_root / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")

    build_windows_section = re.search(
        r"build-windows:\n(?P<section>.*?)(?:\n  release:|\Z)",
        content,
        re.DOTALL,
    )
    assert build_windows_section, "build.yml must define a build-windows job"

    section = build_windows_section.group("section")
    assert "Download libmpv runtime" in section
    assert "Invoke-WebRequest" in section
    assert "http://46.38.157.230/libmpv-2.dll" in section
    assert "mpv\\libmpv-2.dll" in section
    assert "choco install mpv" not in section


def test_linux_workflow_uses_explicit_fcitx5_cache_restore_and_save():
    """Linux CI should restore and save the fcitx5 plugin cache explicitly."""
    repo_root = Path(__file__).resolve().parents[1]
    content = (repo_root / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")

    build_linux_section = re.search(
        r"build-linux:\n(?P<section>.*?)(?:\n  build-macos:|\Z)",
        content,
        re.DOTALL,
    )
    assert build_linux_section, "build.yml must define a build-linux job"

    section = build_linux_section.group("section")
    assert "Restore fcitx5 Qt6 plugin cache" in section
    assert "uses: actions/cache/restore@v4" in section
    assert "Save fcitx5 Qt6 plugin cache" in section
    assert "uses: actions/cache/save@v4" in section
    assert "uses: actions/cache@v4" not in section


def test_collect_data_files_includes_builtin_plugins(tmp_path, monkeypatch):
    """Packaged builds must include builtin plugins for runtime discovery."""
    repo_root = tmp_path / "repo"
    builtin_plugin = repo_root / "plugins" / "builtin" / "demo"
    builtin_plugin.mkdir(parents=True)
    (builtin_plugin / "plugin.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(build, "PROJECT_ROOT", repo_root)

    data_files = build.collect_data_files()

    assert (str(repo_root / "plugins" / "builtin"), "plugins/builtin") in data_files
