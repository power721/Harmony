from unittest.mock import Mock

from services.ai.acoustid_service import AcoustIDService


def test_enhance_track_uses_injected_metadata_service(monkeypatch):
    monkeypatch.setattr(
        AcoustIDService,
        "identify_track",
        classmethod(lambda cls, file_path, api_key: [{"score": 0.9, "title": "Song", "artist": "Artist"}]),
    )
    monkeypatch.setattr(
        AcoustIDService,
        "get_best_match",
        classmethod(lambda cls, results, prefer_chinese=True: results[0]),
    )
    metadata_service = Mock()

    result = AcoustIDService.enhance_track(
        "/tmp/song.mp3",
        "api-key",
        current_metadata={"album": "Album"},
        update_file=True,
        metadata_service=metadata_service,
    )

    assert result is not None
    metadata_service.save_metadata.assert_called_once_with(
        "/tmp/song.mp3",
        title="Song",
        artist="Artist",
        album="Album",
    )
