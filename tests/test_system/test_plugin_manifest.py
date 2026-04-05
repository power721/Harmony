import pytest

from harmony_plugin_api.manifest import PluginManifest, PluginManifestError
from harmony_plugin_api.online import PluginTrack
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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("entrypoint", None),
        ("capabilities", "cover"),
    ],
)
def test_manifest_rejects_invalid_field_types(field, value):
    payload = {
        "id": "broken",
        "name": "Broken Plugin",
        "version": "1.0.0",
        "api_version": "1",
        "entrypoint": "plugin_main.py",
        "entry_class": "BrokenPlugin",
        "capabilities": ["sidebar", "cover"],
        "min_app_version": "0.1.0",
    }
    payload[field] = value

    with pytest.raises(PluginManifestError):
        PluginManifest.from_dict(payload)


def test_sidebar_spec_page_factory_contract():
    calls = []

    def page_factory(context, parent):
        calls.append((context, parent))
        return {"ok": True}

    spec = SidebarEntrySpec(
        plugin_id="qqmusic",
        entry_id="qqmusic.sidebar",
        title="QQ Music",
        order=80,
        icon_name="GLOBE",
        page_factory=page_factory,
    )

    created = spec.page_factory("ctx", "parent")

    assert calls == [("ctx", "parent")]
    assert created == {"ok": True}


def test_online_module_exports_plugin_track():
    track = PluginTrack(
        track_id="1",
        title="Song",
        artist="Singer",
    )

    assert track.track_id == "1"
