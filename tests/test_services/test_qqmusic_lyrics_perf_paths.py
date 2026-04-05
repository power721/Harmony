"""QQ Music lyrics helper behavior tests for transformed list paths."""

from services.lyrics import qqmusic_lyrics


def test_search_artist_from_qqmusic_builds_expected_fields(monkeypatch):
    class _FakeClient:
        @staticmethod
        def search_artist(_artist_name, _limit):
            return [{"mid": "s1", "name": "Singer 1", "albumNum": 12}]

    monkeypatch.setattr(qqmusic_lyrics, "_get_client", lambda: _FakeClient())

    results = qqmusic_lyrics.search_artist_from_qqmusic("Singer 1", limit=5)

    assert results == [
        {
            "id": "s1",
            "name": "Singer 1",
            "singer_mid": "s1",
            "album_count": 12,
            "source": "qqmusic",
        }
    ]


def test_get_client_uses_module_cache_without_bootstrap(monkeypatch):
    class _FakeClient:
        def __init__(self):
            self.created = True

    monkeypatch.setattr("app.bootstrap.Bootstrap.instance", lambda: (_ for _ in ()).throw(AssertionError("bootstrap should not be used")))
    monkeypatch.setattr(qqmusic_lyrics, "QQMusicClient", _FakeClient)
    monkeypatch.setattr(qqmusic_lyrics, "_shared_client", None, raising=False)

    client = qqmusic_lyrics._get_client()

    assert isinstance(client, _FakeClient)


def test_credential_helpers_prefer_plugin_settings_namespace():
    class _Config:
        def __init__(self):
            self.values = {
                ("qqmusic", "credential"): {"musicid": "1", "musickey": "secret"},
            }
            self.saved = []

        def get_plugin_setting(self, plugin_id, key, default=None):
            return self.values.get((plugin_id, key), default)

        def set_plugin_setting(self, plugin_id, key, value):
            self.saved.append((plugin_id, key, value))

    config = _Config()

    assert qqmusic_lyrics._get_credential_from_config(config)["musickey"] == "secret"

    payload = {"musicid": "2", "musickey": "new"}
    qqmusic_lyrics._save_credential_to_config(config, payload)

    assert config.saved == [("qqmusic", "credential", payload)]
