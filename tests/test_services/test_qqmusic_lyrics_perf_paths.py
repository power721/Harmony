"""QQ Music plugin runtime helper behavior tests."""

from plugins.builtin.qqmusic.lib import runtime_client


def test_search_artist_from_qqmusic_builds_expected_fields(monkeypatch):
    class _FakeClient:
        @staticmethod
        def search_artist(_artist_name, _limit):
            return [{"mid": "s1", "name": "Singer 1", "albumNum": 12}]

    monkeypatch.setattr(runtime_client, "get_shared_client", lambda: _FakeClient())

    client = runtime_client.get_shared_client()
    artists = client.search_artist("Singer 1", 5)
    results = [
        {
            "id": artist.get("mid", ""),
            "name": artist.get("name", ""),
            "singer_mid": artist.get("mid", ""),
            "album_count": artist.get("albumNum", 0),
            "source": "qqmusic",
        }
        for artist in artists
    ]

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
    monkeypatch.setattr(runtime_client, "QQMusicClient", _FakeClient)
    monkeypatch.setattr(runtime_client, "_shared_client", None, raising=False)

    client = runtime_client.get_shared_client()

    assert isinstance(client, _FakeClient)


def test_credential_helpers_prefer_plugin_settings_namespace():
    class _Config:
        def __init__(self):
            self.values = {
                ("qqmusic", "credential"): '{"musicid":"1","musickey":"secret"}',
            }
            self.saved = []

        def get_plugin_secret(self, plugin_id, key, default=""):
            return self.values.get((plugin_id, key), default)

        def set_plugin_secret(self, plugin_id, key, value):
            self.saved.append((plugin_id, key, value))

    config = _Config()

    assert runtime_client.get_credential_from_config(config)["musickey"] == "secret"

    payload = {"musicid": "2", "musickey": "new"}
    runtime_client.save_credential_to_config(config, payload)

    assert config.saved == [("qqmusic", "credential", '{"musicid": "2", "musickey": "new"}')]
