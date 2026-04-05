from pathlib import Path

import pytest

from system.plugins.errors import PluginInstallError
from system.plugins.installer import audit_plugin_imports


def test_import_audit_rejects_host_internal_import(tmp_path: Path):
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    (plugin_root / "plugin_main.py").write_text(
        "from services.lyrics.qqmusic_lyrics import QQMusicClient\n",
        encoding="utf-8",
    )

    with pytest.raises(PluginInstallError):
        audit_plugin_imports(plugin_root)
