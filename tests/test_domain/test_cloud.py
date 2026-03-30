"""
Tests for Cloud domain models.
"""

import pytest
from datetime import datetime
from domain.cloud import CloudAccount, CloudFile


class TestCloudAccount:
    """Test CloudAccount domain model."""

    def test_default_initialization(self):
        """Test cloud account with default values."""
        account = CloudAccount()
        assert account.id is None
        assert account.provider == ""
        assert account.account_name == ""
        assert account.account_email == ""
        assert account.access_token == ""
        assert account.refresh_token == ""
        assert account.token_expires_at is None
        assert account.is_active is True
        assert account.last_folder_path == "/"
        assert account.last_fid_path == "0"
        assert account.last_playing_fid == ""
        assert account.last_position == 0.0
        assert account.last_playing_local_path == ""
        assert isinstance(account.created_at, datetime)
        assert isinstance(account.updated_at, datetime)

    def test_quark_account_initialization(self):
        """Test Quark cloud account."""
        account = CloudAccount(
            id=1,
            provider="quark",
            account_name="My Quark",
            account_email="user@example.com",
            access_token="token123",
        )
        assert account.provider == "quark"
        assert account.account_name == "My Quark"
        assert account.account_email == "user@example.com"

    def test_baidu_account_initialization(self):
        """Test Baidu cloud account."""
        account = CloudAccount(
            id=2,
            provider="baidu",
            account_name="My Baidu",
        )
        assert account.provider == "baidu"
        assert account.account_name == "My Baidu"

    def test_created_at_auto_set(self):
        """Test created_at is automatically set."""
        before = datetime.now()
        account = CloudAccount()
        after = datetime.now()
        assert before <= account.created_at <= after

    def test_updated_at_auto_set(self):
        """Test updated_at is automatically set."""
        before = datetime.now()
        account = CloudAccount()
        after = datetime.now()
        assert before <= account.updated_at <= after


class TestCloudFile:
    """Test CloudFile domain model."""

    def test_default_initialization(self):
        """Test cloud file with default values."""
        cloud_file = CloudFile()
        assert cloud_file.id is None
        assert cloud_file.account_id == 0
        assert cloud_file.file_id == ""
        assert cloud_file.parent_id == ""
        assert cloud_file.name == ""
        assert cloud_file.file_type == ""
        assert cloud_file.size is None
        assert cloud_file.mime_type is None
        assert cloud_file.duration is None
        assert cloud_file.metadata is None
        assert cloud_file.local_path is None
        assert isinstance(cloud_file.created_at, datetime)
        assert isinstance(cloud_file.updated_at, datetime)  # updated_at is auto-set

    def test_audio_file_initialization(self, sample_cloud_file_data):
        """Test cloud file for audio."""
        cloud_file = CloudFile(**sample_cloud_file_data)
        assert cloud_file.id == 1
        assert cloud_file.account_id == 1
        assert cloud_file.file_id == "quark_12345"
        assert cloud_file.name == "cloud_song.mp3"
        assert cloud_file.file_type == "audio"
        assert cloud_file.size == 5242880
        assert cloud_file.duration == 240.0

    def test_folder_initialization(self):
        """Test cloud file as folder."""
        folder = CloudFile(
            account_id=1,
            file_id="folder_123",
            parent_id="",
            name="My Music",
            file_type="folder",
        )
        assert folder.file_type == "folder"
        assert folder.name == "My Music"

    def test_created_at_auto_set(self):
        """Test created_at is automatically set."""
        before = datetime.now()
        cloud_file = CloudFile()
        after = datetime.now()
        assert before <= cloud_file.created_at <= after

    def test_updated_at_can_be_set(self):
        """Test updated_at can be explicitly set."""
        specific_time = datetime(2024, 1, 1, 12, 0, 0)
        cloud_file = CloudFile(updated_at=specific_time)
        assert cloud_file.updated_at == specific_time

    def test_local_path_set_and_get(self):
        """Test local_path can be set and retrieved."""
        cf = CloudFile()
        assert cf.local_path is None
        cf.local_path = "/downloads/song.mp3"
        assert cf.local_path == "/downloads/song.mp3"

    def test_metadata_field(self):
        """Test metadata JSON field."""
        cf = CloudFile(metadata='{"key": "value"}')
        assert cf.metadata == '{"key": "value"}'

    def test_size_and_duration_fields(self):
        """Test size and duration fields."""
        cf = CloudFile(size=1024000, duration=240.5, mime_type="audio/mpeg")
        assert cf.size == 1024000
        assert cf.duration == 240.5
        assert cf.mime_type == "audio/mpeg"

    def test_timestamp_consistency(self):
        """Test updated_at >= created_at by default."""
        cf = CloudFile()
        assert cf.updated_at >= cf.created_at


class TestCloudAccountAdditional:
    """Additional CloudAccount tests for uncovered fields."""

    def test_is_active_default_and_set_false(self):
        """Test is_active defaults to True, can be set to False."""
        account = CloudAccount()
        assert account.is_active is True

        account = CloudAccount(is_active=False)
        assert account.is_active is False

    def test_custom_last_folder_path(self):
        """Test custom last_folder_path."""
        account = CloudAccount(last_folder_path="/音乐/test")
        assert account.last_folder_path == "/音乐/test"

    def test_custom_last_fid_path(self):
        """Test custom last_fid_path."""
        account = CloudAccount(last_fid_path="/fid1/fid2/fid3")
        assert account.last_fid_path == "/fid1/fid2/fid3"

    def test_set_last_playing_fid(self):
        """Test setting last_playing_fid."""
        account = CloudAccount(last_playing_fid="file_abc_123")
        assert account.last_playing_fid == "file_abc_123"

    def test_set_last_position(self):
        """Test setting last_position."""
        account = CloudAccount(last_position=45.5)
        assert account.last_position == 45.5

    def test_set_last_playing_local_path(self):
        """Test setting last_playing_local_path."""
        account = CloudAccount(last_playing_local_path="/cache/song.mp3")
        assert account.last_playing_local_path == "/cache/song.mp3"

    def test_set_token_expires_at(self):
        """Test setting token_expires_at."""
        future = datetime(2025, 12, 31, 23, 59, 59)
        account = CloudAccount(token_expires_at=future)
        assert account.token_expires_at == future

    def test_set_refresh_token(self):
        """Test setting refresh_token."""
        account = CloudAccount(refresh_token="refresh_abc_123")
        assert account.refresh_token == "refresh_abc_123"

    def test_account_timestamp_consistency(self):
        """Test updated_at >= created_at by default."""
        account = CloudAccount()
        assert account.updated_at >= account.created_at
