from services.cloud.baidu_service import BaiduDriveService


class _MockResponse:
    def __init__(self, payload, text="ok"):
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


def test_delete_files_success(monkeypatch):
    captured = {}

    class _MockSession:
        def post(self, url, params=None, data=None, headers=None, timeout=None):
            captured["url"] = url
            captured["params"] = params
            captured["data"] = data
            captured["headers"] = headers
            return _MockResponse({"errno": 0})

    monkeypatch.setattr("services.cloud.baidu_service._rate_limit", lambda: None)
    monkeypatch.setattr(
        BaiduDriveService,
        "_get_session",
        classmethod(lambda cls: _MockSession()),
    )

    ok, updated = BaiduDriveService.delete_files(
        "BDUSS=abc; STOKEN=def; csrfToken=token123",
        ["/music/a.mp3", "/music/b.mp3"],
    )

    assert ok is True
    assert updated is None
    assert captured["url"] == "https://pan.baidu.com/api/filemanager"
    assert captured["params"]["opera"] == "delete"
    assert captured["params"]["async"] == "2"
    assert captured["params"]["onnest"] == "fail"
    assert captured["params"]["bdstoken"] == "token123"
    assert captured["params"]["newVerify"] == "1"
    assert captured["params"]["clienttype"] == "0"
    assert captured["params"]["app_id"] == "250528"
    assert captured["params"]["web"] == "1"
    assert captured["data"]["filelist"] == '["/music/a.mp3", "/music/b.mp3"]'
    assert captured["headers"]["X-Requested-With"] == "XMLHttpRequest"


def test_delete_files_failure(monkeypatch):
    class _MockSession:
        def post(self, *args, **kwargs):
            return _MockResponse({"errno": 404})

    monkeypatch.setattr("services.cloud.baidu_service._rate_limit", lambda: None)
    monkeypatch.setattr(
        BaiduDriveService,
        "_get_session",
        classmethod(lambda cls: _MockSession()),
    )

    ok, updated = BaiduDriveService.delete_files("BDUSS=abc", "/music/missing.mp3")
    assert ok is False
    assert updated is None


class _MockStreamResponse:
    headers = {"content-length": "3"}

    def iter_content(self, chunk_size=8192):
        yield b"abc"


class _MockStreamContext:
    def __enter__(self):
        return _MockStreamResponse()

    def __exit__(self, exc_type, exc, tb):
        return False


def test_download_file_returns_true_when_file_written(monkeypatch, tmp_path):
    class _MockHttpClient:
        def stream(self, method, url, headers=None, timeout=None):
            return _MockStreamContext()

    monkeypatch.setattr(
        "services.cloud.baidu_service.HttpClient.shared",
        classmethod(lambda cls, **kwargs: _MockHttpClient()),
    )

    dest = tmp_path / "song.mp3"
    ok = BaiduDriveService.download_file("https://example.com/song.mp3", str(dest), "BDUSS=abc")

    assert ok is True
    assert dest.read_bytes() == b"abc"
