from services.cloud.share_search_service import ShareSearchService


class _FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data


class _FakeHttpClient:
    def __init__(self, response):
        self._response = response

    def get(self, url, params=None, timeout=10):
        assert "api/search" in url
        assert params is not None
        return self._response



def test_search_parses_results(monkeypatch):
    payload = {
        "limit": 20,
        "page": 1,
        "total": 1,
        "totalPages": 1,
        "songs": [
            {
                "id": "18178",
                "title": "黄霄雲《玫瑰星云》[FLAC/MP3-320K] [百度网盘] [蓝奏云] [夸克网盘]",
                "artist": "黄霄雲",
                "name": "玫瑰星云",
                "link0": "https://pan.baidu.com/s/xx?pwd=aaaa",
                "link1": "https://hifiti.lanzouw.com/xx?pwd=bbbb",
                "link2": "https://pan.quark.cn/s/abcd1234#/list/share",
            }
        ],
    }

    fake_client = _FakeHttpClient(_FakeResponse(payload))
    monkeypatch.setattr(ShareSearchService, "_http_client", fake_client)

    result = ShareSearchService.search("玫瑰星云")

    assert result.total == 1
    assert len(result.songs) == 1
    assert result.songs[0].artist == "黄霄雲"
    assert result.songs[0].quark_link == "https://pan.quark.cn/s/abcd1234#/list/share"
    assert result.songs[0].has_quark_link is True


def test_search_without_quark_link_still_visible(monkeypatch):
    payload = {
        "limit": 20,
        "page": 1,
        "total": 1,
        "totalPages": 1,
        "songs": [
            {
                "id": "1",
                "title": "Only Baidu",
                "artist": "A",
                "name": "B",
                "link0": "https://pan.baidu.com/s/xx?pwd=aaaa",
            }
        ],
    }

    monkeypatch.setattr(
        ShareSearchService,
        "_http_client",
        _FakeHttpClient(_FakeResponse(payload)),
    )

    result = ShareSearchService.search("Only")
    assert len(result.songs) == 1
    assert result.songs[0].has_quark_link is False
    assert result.songs[0].quark_link is None
