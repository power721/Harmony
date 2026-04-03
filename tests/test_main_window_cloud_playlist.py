from types import SimpleNamespace

from ui.windows.main_window import MainWindow


class _PlaybackMock:
    def __init__(self):
        self.play_cloud_playlist_calls = []
        self.on_cloud_file_downloaded_calls = []

    def play_cloud_playlist(self, cloud_files, index, account, temp_path, start_position):
        self.play_cloud_playlist_calls.append((cloud_files, index, account, temp_path, start_position))

    def on_cloud_file_downloaded(self, file_id, local_path):
        self.on_cloud_file_downloaded_calls.append((file_id, local_path))


def test_play_cloud_playlist_should_not_duplicate_download_callback():
    mw = MainWindow.__new__(MainWindow)
    account = SimpleNamespace(id=1, provider="quark")
    cloud_files = [SimpleNamespace(file_id="fid_1")]

    mw._cloud_drive_view = SimpleNamespace(_current_account=account)
    mw._playback = _PlaybackMock()
    mw._current_cloud_account = None

    mw._play_cloud_playlist("/tmp/a.mp3", 0, cloud_files, 0.0)

    assert len(mw._playback.play_cloud_playlist_calls) == 1
    # Avoid duplicate metadata/download pipeline for first file.
    assert mw._playback.on_cloud_file_downloaded_calls == []
