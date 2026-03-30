"""
Tests for HttpClient infrastructure component.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from infrastructure.network.http_client import HttpClient


class TestHttpClient:
    """Test HttpClient class."""

    def test_initialization_default(self):
        """Test HttpClient initialization with defaults."""
        client = HttpClient()
        assert client.timeout == 30
        assert isinstance(client.default_headers, dict)
        assert "User-Agent" in client.default_headers

    def test_initialization_custom(self):
        """Test HttpClient initialization with custom values."""
        custom_headers = {"User-Agent": "TestAgent"}
        client = HttpClient(default_headers=custom_headers, timeout=60)
        assert client.timeout == 60
        assert client.default_headers == custom_headers

    def test_initialization_none_headers(self):
        """Test HttpClient with None headers uses defaults."""
        client = HttpClient(default_headers=None)
        assert isinstance(client.default_headers, dict)
        assert "User-Agent" in client.default_headers

    @patch('infrastructure.network.http_client.requests.Session')
    def test_get_request(self, mock_session_class):
        """Test GET request."""
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = HttpClient()
        response = client.get("http://example.com")

        mock_session.get.assert_called_once()
        assert response.status_code == 200

    @patch('infrastructure.network.http_client.requests.Session')
    def test_post_request_json(self, mock_session_class):
        """Test POST request with JSON."""
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 201
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = HttpClient()
        response = client.post("http://example.com", json={"key": "value"})

        mock_session.post.assert_called_once()
        assert response.status_code == 201

    def test_has_download_method(self):
        """Test HttpClient has download method."""
        client = HttpClient()
        assert hasattr(client, 'download')
        assert callable(client.download)

    def test_default_headers_merge_with_request(self):
        """Test that default headers are merged with request headers."""
        client = HttpClient(
            default_headers={"Authorization": "Bearer token"},
            timeout=30
        )
        assert client.default_headers["Authorization"] == "Bearer token"

    def test_timeout_setting(self):
        """Test timeout can be set."""
        client = HttpClient(timeout=120)
        assert client.timeout == 120

    def test_close_method(self):
        """Test close method releases resources."""
        client = HttpClient()
        assert hasattr(client, 'close')
        assert callable(client.close)
        # Should not raise
        client.close()

    def test_context_manager(self):
        """Test HttpClient can be used as context manager."""
        with HttpClient() as client:
            assert client is not None


class TestGetContent:
    """Test HttpClient.get_content method."""

    @patch('infrastructure.network.http_client.requests.Session')
    def test_get_content_success(self, mock_session_class):
        """Test get_content returns bytes on success."""
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.content = b"binary data"
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = HttpClient()
        result = client.get_content("http://example.com/data")

        assert result == b"binary data"
        mock_session.get.assert_called_once()

    @patch('infrastructure.network.http_client.requests.Session')
    def test_get_content_with_params(self, mock_session_class):
        """Test get_content passes query parameters."""
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.content = b'response'
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = HttpClient()
        result = client.get_content("http://example.com", params={"key": "value"})

        assert result == b'response'
        call_kwargs = mock_session.get.call_args[1]
        assert call_kwargs['params'] == {"key": "value"}

    @patch('infrastructure.network.http_client.requests.Session')
    def test_get_content_with_custom_headers(self, mock_session_class):
        """Test get_content passes custom headers."""
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.content = b'response'
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = HttpClient()
        result = client.get_content("http://example.com", headers={"X-Custom": "test"})

        assert result == b'response'
        call_kwargs = mock_session.get.call_args[1]
        assert call_kwargs['headers'] == {"X-Custom": "test"}

    @patch('infrastructure.network.http_client.requests.Session')
    def test_get_content_with_custom_timeout(self, mock_session_class):
        """Test get_content uses custom timeout."""
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.content = b'response'
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = HttpClient(timeout=30)
        result = client.get_content("http://example.com", timeout=60)

        assert result == b'response'
        call_kwargs = mock_session.get.call_args[1]
        assert call_kwargs['timeout'] == 60

    @patch('infrastructure.network.http_client.requests.Session')
    def test_get_content_http_error_returns_none(self, mock_session_class):
        """Test get_content returns None on HTTP error."""
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = HttpClient()
        result = client.get_content("http://example.com/notfound")

        assert result is None

    @patch('infrastructure.network.http_client.requests.Session')
    def test_get_content_connection_error_returns_none(self, mock_session_class):
        """Test get_content returns None on connection error."""
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Connection refused")
        mock_session_class.return_value = mock_session

        client = HttpClient()
        result = client.get_content("http://example.com")

        assert result is None

    @patch('infrastructure.network.http_client.requests.Session')
    def test_get_content_timeout_error_returns_none(self, mock_session_class):
        """Test get_content returns None on timeout."""
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Request timeout")
        mock_session_class.return_value = mock_session

        client = HttpClient(timeout=1)
        result = client.get_content("http://example.com/slow")

        assert result is None


class TestDownload:
    """Test HttpClient.download method."""

    @patch('infrastructure.network.http_client.requests.Session')
    def test_download_success(self, mock_session_class, tmp_path):
        """Test successful file download."""
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-length': '1024'}
        mock_response.raise_for_status = Mock()
        # Simulate streaming content in two chunks
        mock_response.iter_content.return_value = [b'chunk1_data', b'chunk2_data']
        mock_response.close = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        dest = str(tmp_path / "downloaded_file.bin")

        client = HttpClient()
        result = client.download("http://example.com/file", dest)

        assert result is True
        assert Path(dest).exists()
        assert Path(dest).read_bytes() == b'chunk1_datachunk2_data'
        mock_response.close.assert_called_once()

    @patch('infrastructure.network.http_client.requests.Session')
    def test_download_with_progress_callback(self, mock_session_class, tmp_path):
        """Test download calls progress callback."""
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-length': '20'}
        mock_response.raise_for_status = Mock()
        mock_response.iter_content.return_value = [b'12345', b'67890']
        mock_response.close = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        dest = str(tmp_path / "file.bin")
        progress_calls = []

        def on_progress(current, total):
            progress_calls.append((current, total))

        client = HttpClient()
        result = client.download("http://example.com/file", dest,
                                 progress_callback=on_progress)

        assert result is True
        assert len(progress_calls) == 2
        assert progress_calls[0] == (5, 20)
        assert progress_calls[1] == (10, 20)

    @patch('infrastructure.network.http_client.requests.Session')
    def test_download_with_custom_chunk_size(self, mock_session_class, tmp_path):
        """Test download respects custom chunk size."""
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-length': '6'}
        mock_response.raise_for_status = Mock()
        # Server returns small pieces regardless of chunk_size
        mock_response.iter_content.return_value = [b'abc', b'def']
        mock_response.close = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        dest = str(tmp_path / "file.bin")

        client = HttpClient()
        result = client.download("http://example.com/file", dest, chunk_size=1024)

        assert result is True
        # Verify chunk_size was passed to iter_content
        call_kwargs = mock_response.iter_content.call_args[1]
        assert call_kwargs['chunk_size'] == 1024

    @patch('infrastructure.network.http_client.requests.Session')
    def test_download_failure_cleans_up_file(self, mock_session_class, tmp_path):
        """Test download removes incomplete file on failure."""
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-length': '1024'}
        mock_response.raise_for_status = Mock()
        mock_response.iter_content.side_effect = Exception("Network error")
        mock_response.close = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        dest = str(tmp_path / "incomplete.bin")

        client = HttpClient()
        result = client.download("http://example.com/file", dest)

        assert result is False
        # File should be cleaned up even if partially written
        assert not Path(dest).exists()

    @patch('infrastructure.network.http_client.requests.Session')
    def test_download_http_error(self, mock_session_class, tmp_path):
        """Test download returns False on HTTP error."""
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("403 Forbidden")
        mock_response.close = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        dest = str(tmp_path / "forbidden.bin")

        client = HttpClient()
        result = client.download("http://example.com/forbidden", dest)

        assert result is False
        assert not Path(dest).exists()

    @patch('infrastructure.network.http_client.requests.Session')
    def test_download_with_custom_headers(self, mock_session_class, tmp_path):
        """Test download passes custom headers."""
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-length': '5'}
        mock_response.raise_for_status = Mock()
        mock_response.iter_content.return_value = [b'hello']
        mock_response.close = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        dest = str(tmp_path / "file.bin")

        client = HttpClient()
        result = client.download("http://example.com/file", dest,
                                 headers={"Authorization": "Bearer token"})

        assert result is True
        call_kwargs = mock_session.get.call_args[1]
        assert call_kwargs['headers'] == {"Authorization": "Bearer token"}

    @patch('infrastructure.network.http_client.requests.Session')
    def test_download_response_closed_in_finally(self, mock_session_class, tmp_path):
        """Test download always closes response even on success."""
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-length': '4'}
        mock_response.raise_for_status = Mock()
        mock_response.iter_content.return_value = [b'data']
        mock_response.close = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        dest = str(tmp_path / "file.bin")

        client = HttpClient()
        client.download("http://example.com/file", dest)

        mock_response.close.assert_called_once()

    @patch('infrastructure.network.http_client.requests.Session')
    def test_download_with_missing_content_length(self, mock_session_class, tmp_path):
        """Test download works when content-length header is missing."""
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}  # No content-length
        mock_response.raise_for_status = Mock()
        mock_response.iter_content.return_value = [b'data']
        mock_response.close = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        dest = str(tmp_path / "file.bin")
        progress_calls = []

        def on_progress(current, total):
            progress_calls.append((current, total))

        client = HttpClient()
        result = client.download("http://example.com/file", dest,
                                 progress_callback=on_progress)

        assert result is True
        # total_size should be 0 when content-length is missing
        assert progress_calls[0] == (4, 0)
