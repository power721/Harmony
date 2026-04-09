from types import SimpleNamespace
from unittest.mock import Mock

from services.library.file_organization_service import FileOrganizationService


def test_organize_tracks_reports_rollback_failure(monkeypatch, tmp_path):
    source_audio = tmp_path / "source.mp3"
    source_lyrics = tmp_path / "source.lrc"
    source_audio.write_bytes(b"audio")
    source_lyrics.write_text("lyrics", encoding="utf-8")
    target_dir = tmp_path / "organized"
    target_dir.mkdir()

    track = SimpleNamespace(
        id=1,
        title="Song",
        artist="Artist",
        album="Album",
        path=str(source_audio),
        cloud_file_id=None,
    )
    track_repo = Mock()
    track_repo.get_by_ids.return_value = [track]
    track_repo.update.return_value = False
    event_bus = SimpleNamespace(tracks_organized=SimpleNamespace(emit=Mock()))

    service = FileOrganizationService(
        track_repo=track_repo,
        cloud_repo=Mock(),
        event_bus=event_bus,
        queue_repo=Mock(),
    )

    target_audio = target_dir / "Song.mp3"
    target_lyrics = target_dir / "Song.lrc"

    monkeypatch.setattr(
        "services.library.file_organization_service.calculate_target_path",
        lambda _track, _target_dir: (target_audio, target_lyrics),
    )
    monkeypatch.setattr(
        "services.library.file_organization_service.ensure_directory",
        lambda _path: True,
    )

    move_calls = {"count": 0}

    def fake_move(_src: str, _dst: str):
        move_calls["count"] += 1
        if move_calls["count"] <= 2:
            return None
        raise OSError("rollback failed")

    monkeypatch.setattr("services.library.file_organization_service.shutil.move", fake_move)

    results = service.organize_tracks([1], str(target_dir))

    assert results["failed"] == 1
    assert any("文件回滚失败" in error for error in results["errors"])
