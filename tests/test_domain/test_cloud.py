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
