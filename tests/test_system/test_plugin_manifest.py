import pytest

from harmony_plugin_api.manifest import PluginManifest, PluginManifestError
from harmony_plugin_api.registry_types import SidebarEntrySpec


def test_manifest_accepts_cover_capability():
    manifest = PluginManifest.from_dict(
        {
            "id": "qqmusic",
            "name": "QQ Music",
            "version": "1.0.0",
            "api_version": "1",
            "entrypoint": "plugin_main.py",
            "entry_class": "QQMusicPlugin",
            "capabilities": [
                "sidebar",
                "settings_tab",
                "lyrics_source",
                "cover",
                "online_music_provider",
            ],
            "min_app_version": "0.1.0",
        }
    )

    assert manifest.id == "qqmusic"
    assert "cover" in manifest.capabilities


def test_manifest_rejects_unknown_capability():
    with pytest.raises(PluginManifestError):
        PluginManifest.from_dict(
            {
                "id": "broken",
                "name": "Broken Plugin",
                "version": "1.0.0",
                "api_version": "1",
                "entrypoint": "plugin_main.py",
                "entry_class": "BrokenPlugin",
                "capabilities": ["sidebar", "banana"],
                "min_app_version": "0.1.0",
            }
        )


def test_sidebar_spec_requires_widget_factory():
    spec = SidebarEntrySpec(
        plugin_id="qqmusic",
        entry_id="qqmusic.sidebar",
        title="QQ Music",
        order=80,
        icon_name="GLOBE",
        page_factory=lambda _context, _parent: object(),
    )

    assert spec.entry_id == "qqmusic.sidebar"
