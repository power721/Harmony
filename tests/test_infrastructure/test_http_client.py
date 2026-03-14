"""
Tests for HttpClient infrastructure component.
"""

import pytest
from unittest.mock import Mock, patch
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

    @patch('infrastructure.network.http_client.requests.get')
    def test_get_request(self, mock_get):
        """Test GET request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        client = HttpClient()
        response = client.get("http://example.com")

        mock_get.assert_called_once()
        assert response.status_code == 200

    @patch('infrastructure.network.http_client.requests.post')
    def test_post_request_json(self, mock_post):
        """Test POST request with JSON."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        client = HttpClient()
        response = client.post("http://example.com", json={"key": "value"})

        mock_post.assert_called_once()
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
