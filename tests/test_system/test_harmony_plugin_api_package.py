from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import subprocess


PACKAGE_ROOT = Path("packages/harmony-plugin-api")
PACKAGE_SRC = PACKAGE_ROOT / "src" / "harmony_plugin_api"
FORBIDDEN_ROOT_IMPORTS = {
    "app",
    "domain",
    "services",
    "repositories",
    "infrastructure",
    "system",
    "ui",
}


def test_harmony_plugin_api_package_has_standalone_pyproject():
    pyproject = PACKAGE_ROOT / "pyproject.toml"

    assert pyproject.exists()
    content = pyproject.read_text(encoding="utf-8")
    assert 'name = "harmony-plugin-api"' in content
    assert 'version = "0.1.0"' in content


def test_harmony_plugin_api_package_excludes_host_runtime_modules():
    assert PACKAGE_SRC.exists()
    assert (PACKAGE_SRC / "context.py").exists()
    assert not (PACKAGE_SRC / "ui.py").exists()
    assert not (PACKAGE_SRC / "runtime.py").exists()


def test_plugin_context_declares_runtime_bridge_contract():
    context_source = (PACKAGE_SRC / "context.py").read_text(encoding="utf-8")
    tree = ast.parse(context_source, filename=str(PACKAGE_SRC / "context.py"))
    plugin_context = next(
        node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == "PluginContext"
    )
    annotated_fields = [
        node.target.id
        for node in plugin_context.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    ]

    assert "runtime" in annotated_fields


def test_harmony_plugin_api_package_has_no_host_imports():
    assert PACKAGE_SRC.exists()

    violations: list[tuple[Path, list[str]]] = []
    for py_file in PACKAGE_SRC.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            names = None
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    continue
                if node.module:
                    names = [node.module.split(".")[0]]
            if names and any(name in FORBIDDEN_ROOT_IMPORTS for name in names):
                violations.append((py_file, names))

    assert violations == []


def test_harmony_plugin_api_package_can_be_built():
    dist_dir = PACKAGE_ROOT / "dist"
    if not any(path.suffix == ".whl" for path in dist_dir.glob("*.whl")):
        subprocess.run(["uv", "build"], cwd=PACKAGE_ROOT, check=True)
    assert any(path.suffix == ".whl" for path in dist_dir.glob("*.whl"))


def test_runtime_import_resolves_to_installed_harmony_plugin_api():
    spec = importlib.util.find_spec("harmony_plugin_api")

    assert spec is not None
    assert spec.origin is not None
    assert "site-packages/harmony_plugin_api/__init__.py" in spec.origin
