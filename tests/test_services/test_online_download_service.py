from unittest.mock import MagicMock, patch

from services.online.download_service import OnlineDownloadService


class TestOnlineDownloadService:
    @patch("services.online.download_service.EventBus")
    def test_get_cached_path_uses_quality_extension_mapping(self, mock_event_bus, tmp_path):
        """Quality-specific cache paths should use the real container extension."""
        mock_event_bus.instance.return_value = MagicMock()
        service = OnlineDownloadService(download_dir=str(tmp_path))

        assert service.get_cached_path("song", "ogg_320") == str(tmp_path / "song.ogg")
        assert service.get_cached_path("song", "aac_192") == str(tmp_path / "song.m4a")
        assert service.get_cached_path("song", "flac") == str(tmp_path / "song.flac")

    @patch("services.online.download_service.EventBus")
    def test_get_cached_path_prefers_existing_downloaded_file(self, mock_event_bus, tmp_path):
        """Cache lookups should return an existing file even if its suffix differs from requested quality."""
        mock_event_bus.instance.return_value = MagicMock()
        existing_path = tmp_path / "song.ogg"
        existing_path.write_bytes(b"data")

        service = OnlineDownloadService(download_dir=str(tmp_path))

        assert service.is_cached("song", "flac") is True
        assert service.get_cached_path("song", "flac") == str(existing_path)

    @patch("services.online.download_service.EventBus")
    @patch.object(OnlineDownloadService, "_extract_metadata", return_value=None)
    @patch("services.online.download_service.HttpClient.shared")
    def test_download_uses_returned_file_type_instead_of_guessing_url(
        self, mock_http_client_shared, mock_extract_metadata, mock_event_bus, tmp_path
    ):
        """Downloader should use explicit playback file type metadata instead of URL guessing."""
        event_bus = MagicMock()
        mock_event_bus.instance.return_value = event_bus

        response = MagicMock()
        response.headers = {"content-length": "35"}
        response.iter_content.return_value = [b"OggS" + b"\x00" * 24 + b"\x01vorbis"]
        response.raise_for_status.return_value = None
        response.close = MagicMock()

        stream_context = MagicMock()
        stream_context.__enter__.return_value = response
        stream_context.__exit__.return_value = False

        http_client = MagicMock()
        http_client.stream.return_value = stream_context
        mock_http_client_shared.return_value = http_client

        online_service = MagicMock()
        online_service.get_playback_url_info.return_value = {
            "url": "https://example.com/audio.flac",
            "quality": "ogg_320",
            "extension": ".ogg",
        }

        service = OnlineDownloadService(
            online_music_service=online_service,
            download_dir=str(tmp_path),
        )

        local_path = service.download("song", quality="flac")

        assert local_path == str(tmp_path / "song.ogg")
        assert (tmp_path / "song.ogg").exists()
        assert not (tmp_path / "song.flac").exists()
        online_service.get_playback_url_info.assert_called_once_with("song", "flac")
        online_service.get_playback_url.assert_not_called()
        http_client.stream.assert_called_once_with(
            "GET",
            "https://example.com/audio.flac",
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://y.qq.com/',
            },
            timeout=60,
        )
        event_bus.download_completed.emit.assert_called_once_with("song", str(tmp_path / "song.ogg"))
        mock_extract_metadata.assert_called_once_with("song", str(tmp_path / "song.ogg"))
