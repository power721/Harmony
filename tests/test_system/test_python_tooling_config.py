from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_repo_python_version_uses_pyenv_compatible_selector():
    version = (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip()

    assert version
    assert "/" not in version


def test_harmony_plugin_api_release_script_uses_uv_managed_tooling():
    content = (REPO_ROOT / "packages" / "harmony-plugin-api" / "release.sh").read_text(encoding="utf-8")

    assert "uv build" in content
    assert "uv run --with twine twine upload dist/*" in content
    assert "python -m build" not in content
    assert "\ntwine upload dist/*" not in content
