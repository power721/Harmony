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
