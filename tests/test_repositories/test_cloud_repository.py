"""
Tests for SqliteCloudRepository.
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime

from repositories.cloud_repository import SqliteCloudRepository
from domain.cloud import CloudAccount, CloudFile


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Create tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create cloud_accounts table
    cursor.execute("""
        CREATE TABLE cloud_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            account_name TEXT,
            account_email TEXT,
            access_token TEXT,
            refresh_token TEXT,
            token_expires_at TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            last_folder_path TEXT,
            last_fid_path TEXT,
            last_playing_fid TEXT,
            last_position INTEGER DEFAULT 0,
            last_playing_local_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create cloud_files table
    cursor.execute("""
        CREATE TABLE cloud_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            parent_id TEXT,
            name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            size INTEGER,
            mime_type TEXT,
            duration REAL,
            metadata TEXT,
            local_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES cloud_accounts(id)
        )
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture
def cloud_repo(temp_db):
    """Create a cloud repository with temporary database."""
    return SqliteCloudRepository(temp_db)


@pytest.fixture
def sample_account():
    """Create a sample cloud account."""
    return CloudAccount(
        provider="quark",
        account_name="Test Account",
        account_email="test@example.com",
        access_token="token123",
        refresh_token="refresh123",
        is_active=True,
    )


@pytest.fixture
def sample_file():
    """Create a sample cloud file."""
    return CloudFile(
        account_id=1,
        file_id="file_12345",
        parent_id="folder_67890",
        name="test_song.mp3",
        file_type="audio",
        size=5242880,
        mime_type="audio/mpeg",
        duration=180.0,
    )


class TestSqliteCloudRepository:
    """Test SqliteCloudRepository."""

    def test_initialization(self, temp_db):
        """Test repository initialization."""
        repo = SqliteCloudRepository(temp_db)
        assert repo.db_path == temp_db

    # ===== Cloud Account Tests =====

    def test_add_account(self, cloud_repo, sample_account):
        """Test adding a cloud account."""
        account_id = cloud_repo.add_account(sample_account)
        assert account_id > 0

    def test_get_account_by_id(self, cloud_repo, sample_account):
        """Test getting account by ID."""
        account_id = cloud_repo.add_account(sample_account)

        retrieved = cloud_repo.get_account_by_id(account_id)
        assert retrieved is not None
        assert retrieved.provider == "quark"
        assert retrieved.account_name == "Test Account"
        assert retrieved.account_email == "test@example.com"

    def test_get_account_by_id_not_found(self, cloud_repo):
        """Test getting non-existent account."""
        retrieved = cloud_repo.get_account_by_id(99999)
        assert retrieved is None

    def test_get_all_accounts(self, cloud_repo):
        """Test getting all accounts."""
        # Add multiple accounts
        account1 = CloudAccount(provider="quark", account_name="Account 1")
        account2 = CloudAccount(provider="baidu", account_name="Account 2")
        cloud_repo.add_account(account1)
        cloud_repo.add_account(account2)

        accounts = cloud_repo.get_all_accounts()
        assert len(accounts) == 2

    def test_get_all_accounts_empty(self, cloud_repo):
        """Test getting all accounts when empty."""
        accounts = cloud_repo.get_all_accounts()
        assert accounts == []

    def test_update_account(self, cloud_repo, sample_account):
        """Test updating a cloud account."""
        account_id = cloud_repo.add_account(sample_account)

        sample_account.id = account_id
        sample_account.account_name = "Updated Name"
        result = cloud_repo.update_account(sample_account)

        assert result is True

        updated = cloud_repo.get_account_by_id(account_id)
        assert updated.account_name == "Updated Name"

    def test_update_account_no_id(self, cloud_repo, sample_account):
        """Test updating account without ID."""
        result = cloud_repo.update_account(sample_account)
        assert result is False

    def test_delete_account(self, cloud_repo, sample_account):
        """Test deleting a cloud account."""
        account_id = cloud_repo.add_account(sample_account)

        result = cloud_repo.delete_account(account_id)
        assert result is True

        # Verify deletion
        retrieved = cloud_repo.get_account_by_id(account_id)
        assert retrieved is None

    def test_delete_account_not_found(self, cloud_repo):
        """Test deleting non-existent account."""
        result = cloud_repo.delete_account(99999)
        assert result is False

    # ===== Cloud File Tests =====

    def test_add_file(self, cloud_repo, sample_account, sample_file):
        """Test adding a cloud file."""
        account_id = cloud_repo.add_account(sample_account)
        sample_file.account_id = account_id

        file_id = cloud_repo.add_file(sample_file)
        assert file_id > 0

    def test_get_file_by_id(self, cloud_repo, sample_account, sample_file):
        """Test getting file by file_id."""
        account_id = cloud_repo.add_account(sample_account)
        sample_file.account_id = account_id
        cloud_repo.add_file(sample_file)

        retrieved = cloud_repo.get_file_by_id("file_12345")
        assert retrieved is not None
        assert retrieved.name == "test_song.mp3"
        assert retrieved.file_type == "audio"
        assert retrieved.duration == 180.0

    def test_get_file_by_id_not_found(self, cloud_repo):
        """Test getting non-existent file."""
        retrieved = cloud_repo.get_file_by_id("nonexistent")
        assert retrieved is None

    def test_get_files_by_account(self, cloud_repo, sample_account):
        """Test getting all files for an account."""
        account_id = cloud_repo.add_account(sample_account)

        # Add multiple files
        file1 = CloudFile(account_id=account_id, file_id="f1", name="file1.mp3", file_type="audio")
        file2 = CloudFile(account_id=account_id, file_id="f2", name="file2.mp3", file_type="audio")
        cloud_repo.add_file(file1)
        cloud_repo.add_file(file2)

        files = cloud_repo.get_files_by_account(account_id)
        assert len(files) == 2

    def test_get_files_by_account_empty(self, cloud_repo):
        """Test getting files for account with no files."""
        files = cloud_repo.get_files_by_account(1)
        assert files == []

    def test_update_local_path(self, cloud_repo, sample_account, sample_file):
        """Test updating local path for a file."""
        account_id = cloud_repo.add_account(sample_account)
        sample_file.account_id = account_id
        cloud_repo.add_file(sample_file)

        result = cloud_repo.update_local_path("file_12345", "/local/path/song.mp3")
        assert result is True

        updated = cloud_repo.get_file_by_id("file_12345")
        assert updated.local_path == "/local/path/song.mp3"

    def test_update_local_path_not_found(self, cloud_repo):
        """Test updating local path for non-existent file."""
        result = cloud_repo.update_local_path("nonexistent", "/path")
        assert result is False

    def test_delete_account_cascades_files(self, cloud_repo, sample_account, sample_file):
        """Test that deleting account deletes associated files."""
        account_id = cloud_repo.add_account(sample_account)
        sample_file.account_id = account_id
        cloud_repo.add_file(sample_file)

        # Delete account
        cloud_repo.delete_account(account_id)

        # File should be deleted too
        files = cloud_repo.get_files_by_account(account_id)
        assert files == []

    def test_row_to_account(self, cloud_repo, sample_account):
        """Test conversion of row to CloudAccount."""
        account_id = cloud_repo.add_account(sample_account)

        # Get account to test _row_to_account
        retrieved = cloud_repo.get_account_by_id(account_id)

        assert retrieved.id == account_id
        assert retrieved.provider == "quark"
        assert isinstance(retrieved.created_at, str)

    def test_row_to_file(self, cloud_repo, sample_account, sample_file):
        """Test conversion of row to CloudFile."""
        account_id = cloud_repo.add_account(sample_account)
        sample_file.account_id = account_id
        cloud_repo.add_file(sample_file)

        # Get file to test _row_to_file
        retrieved = cloud_repo.get_file_by_id("file_12345")

        assert retrieved.file_id == "file_12345"
        assert retrieved.account_id == account_id
        assert retrieved.name == "test_song.mp3"
