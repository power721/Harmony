import pytest

import harmony_plugin_api as api
import harmony_plugin_api.context as context_module
from typing import get_type_hints
from harmony_plugin_api.cover import PluginArtistCoverSource, PluginCoverSource
from harmony_plugin_api.lyrics import PluginLyricsSource
from harmony_plugin_api.manifest import PluginManifest, PluginManifestError
from harmony_plugin_api.online import PluginOnlineProvider, PluginTrack
from harmony_plugin_api.registry_types import SidebarEntrySpec
from harmony_plugin_api.registry_types import SettingsTabSpec


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


def test_manifest_accepts_requires_restart_on_toggle():
    manifest = PluginManifest.from_dict(
        {
            "id": "qqmusic",
            "name": "QQ Music",
            "version": "1.0.0",
            "api_version": "1",
            "entrypoint": "plugin_main.py",
            "entry_class": "QQMusicPlugin",
            "capabilities": ["sidebar"],
            "min_app_version": "0.1.0",
            "requires_restart_on_toggle": True,
        }
    )

    assert manifest.requires_restart_on_toggle is True


def test_manifest_defaults_requires_restart_on_toggle_to_false():
    manifest = PluginManifest.from_dict(
        {
            "id": "qqmusic",
            "name": "QQ Music",
            "version": "1.0.0",
            "api_version": "1",
            "entrypoint": "plugin_main.py",
            "entry_class": "QQMusicPlugin",
            "capabilities": ["sidebar"],
            "min_app_version": "0.1.0",
        }
    )

    assert manifest.requires_restart_on_toggle is False


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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", ""),
        ("entrypoint", ""),
        ("entry_class", "   "),
    ],
)
def test_manifest_rejects_empty_or_whitespace_required_strings(field, value):
    payload = {
        "id": "qqmusic",
        "name": "QQ Music",
        "version": "1.0.0",
        "api_version": "1",
        "entrypoint": "plugin_main.py",
        "entry_class": "QQMusicPlugin",
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


def test_context_bridges_use_sdk_contract_types():
    module_globals = vars(context_module)
    sidebar_hints = get_type_hints(
        context_module.PluginUiBridge.register_sidebar_entry,
        globalns=module_globals,
    )
    settings_hints = get_type_hints(
        context_module.PluginUiBridge.register_settings_tab,
        globalns=module_globals,
    )
    lyrics_hints = get_type_hints(
        context_module.PluginServiceBridge.register_lyrics_source,
        globalns=module_globals,
    )
    cover_hints = get_type_hints(
        context_module.PluginServiceBridge.register_cover_source,
        globalns=module_globals,
    )
    artist_cover_hints = get_type_hints(
        context_module.PluginServiceBridge.register_artist_cover_source,
        globalns=module_globals,
    )
    provider_hints = get_type_hints(
        context_module.PluginServiceBridge.register_online_music_provider,
        globalns=module_globals,
    )
    media_hints = get_type_hints(
        context_module.PluginServiceBridge.media.fget,
        globalns=module_globals,
    )

    assert sidebar_hints["spec"] == SidebarEntrySpec
    assert settings_hints["spec"] == SettingsTabSpec
    assert lyrics_hints["source"] == PluginLyricsSource
    assert cover_hints["source"] == PluginCoverSource
    assert artist_cover_hints["source"] == PluginArtistCoverSource
    assert provider_hints["provider"] == PluginOnlineProvider
    assert media_hints["return"] is context_module.PluginMediaBridge


def test_package_exports_smoke():
    assert api.PluginManifest is PluginManifest
    assert api.PluginTrack is PluginTrack
    assert api.SidebarEntrySpec is SidebarEntrySpec
