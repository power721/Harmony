"""
Tests for bug fix: Bug 1 - from_track should preserve original track source.

Previously, from_track() hardcoded one online source for all online tracks,
even QUARK/BAIDU tracks that hadn't been downloaded yet.
"""

from domain.playlist_item import PlaylistItem
from domain.track import Track, TrackSource


class TestBug1TrackSourcePreservation:
    """Bug 1: from_track() should use track.source, not a hardcoded provider source."""

    def test_quark_online_track_preserves_source(self):
        """QUARK track with empty path should keep QUARK source."""
        track = Track(
            id=1,
            path="",
            title="Quark Song",
            artist="Artist",
            source=TrackSource.QUARK,
            cloud_file_id="quark_fid",
        )
        item = PlaylistItem.from_track(track)
        assert item.source == TrackSource.QUARK

    def test_baidu_online_track_preserves_source(self):
        """BAIDU track with empty path should keep BAIDU source."""
        track = Track(
            id=2,
            path="",
            title="Baidu Song",
            artist="Artist",
            source=TrackSource.BAIDU,
            cloud_file_id="baidu_fid",
        )
        item = PlaylistItem.from_track(track)
        assert item.source == TrackSource.BAIDU

    def test_online_track_still_online(self):
        """Online track with empty path should still be ONLINE."""
        track = Track(
            id=3,
            path="",
            title="Online Song",
            artist="Artist",
            source=TrackSource.ONLINE,
            online_provider_id="qqmusic",
            cloud_file_id="song_mid",
        )
        item = PlaylistItem.from_track(track)
        assert item.source == TrackSource.ONLINE

    def test_local_track_still_local(self):
        """Local track with path should remain LOCAL."""
        track = Track(
            id=4,
            path="/music/song.mp3",
            title="Local Song",
            source=TrackSource.LOCAL,
        )
        item = PlaylistItem.from_track(track)
        assert item.source == TrackSource.LOCAL
