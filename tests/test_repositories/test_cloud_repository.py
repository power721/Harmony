"""
Tests for SqliteCloudRepository.
"""

import pytest
import sqlite3
import tempfile
import os

from infrastructure.security.secret_store import SecretStore
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
    except Exception:
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
        """Test deleting a cloud account (soft delete)."""
        account_id = cloud_repo.add_account(sample_account)

        result = cloud_repo.delete_account(account_id)
        assert result is True

        # Verify soft deletion - account should still exist but be inactive
        retrieved = cloud_repo.get_account_by_id(account_id)
        assert retrieved is not None
        assert retrieved.is_active is False

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
        """Test that hard deleting account deletes associated files."""
        account_id = cloud_repo.add_account(sample_account)
        sample_file.account_id = account_id
        cloud_repo.add_file(sample_file)

        # Hard delete account
        cloud_repo.hard_delete_account(account_id)

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
        from datetime import datetime
        assert isinstance(retrieved.created_at, datetime)

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


class TestCloudAccountFilterAndCreate:
    """Test account filtering and creation operations."""

    def test_get_all_accounts_by_provider(self, cloud_repo):
        """Test filtering accounts by provider."""
        cloud_repo.add_account(CloudAccount(provider="quark", account_name="Q Account"))
        cloud_repo.add_account(CloudAccount(provider="baidu", account_name="B Account"))
        cloud_repo.add_account(CloudAccount(provider="quark", account_name="Q Account 2"))

        quark_accounts = cloud_repo.get_all_accounts(provider="quark")
        assert len(quark_accounts) == 2
        assert all(a.provider == "quark" for a in quark_accounts)

        baidu_accounts = cloud_repo.get_all_accounts(provider="baidu")
        assert len(baidu_accounts) == 1
        assert baidu_accounts[0].account_name == "B Account"

    def test_get_all_accounts_by_provider_no_match(self, cloud_repo):
        """Test filtering by provider with no matching accounts."""
        cloud_repo.add_account(CloudAccount(provider="quark", account_name="Q Account"))

        result = cloud_repo.get_all_accounts(provider="onedrive")
        assert result == []

    def test_create_account(self, cloud_repo):
        """Test creating an account with minimal fields."""
        account_id = cloud_repo.create_account(
            provider="quark",
            account_name="New Account",
            account_email="new@example.com",
            access_token="new_token",
            refresh_token="new_refresh"
        )
        assert account_id > 0

        account = cloud_repo.get_account_by_id(account_id)
        assert account.provider == "quark"
        assert account.account_name == "New Account"
        assert account.account_email == "new@example.com"
        assert account.access_token == "new_token"
        assert account.refresh_token == "new_refresh"

    def test_create_account_default_refresh(self, cloud_repo):
        """Test creating account without refresh token."""
        account_id = cloud_repo.create_account(
            provider="baidu",
            account_name="Baidu Account",
            account_email="baidu@test.com",
            access_token="token"
        )
        account = cloud_repo.get_account_by_id(account_id)
        assert account.refresh_token == ""

    def test_create_account_encrypts_tokens_at_rest(self, temp_db, tmp_path):
        """Account tokens should be encrypted in the database but returned decrypted."""
        repo = SqliteCloudRepository(
            temp_db,
            secret_store=SecretStore(tmp_path / "secret.key"),
        )

        account_id = repo.create_account(
            provider="quark",
            account_name="Encrypted Account",
            account_email="enc@example.com",
            access_token="plain_access",
            refresh_token="plain_refresh",
        )

        account = repo.get_account_by_id(account_id)
        assert account.access_token == "plain_access"
        assert account.refresh_token == "plain_refresh"

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT access_token, refresh_token FROM cloud_accounts WHERE id = ?",
            (account_id,),
        )
        raw_access_token, raw_refresh_token = cursor.fetchone()
        conn.close()

        assert raw_access_token != "plain_access"
        assert raw_refresh_token != "plain_refresh"

    def test_update_account_token_encrypts_new_values_at_rest(self, temp_db, sample_account, tmp_path):
        """Updating tokens should rewrite the stored values in encrypted form."""
        repo = SqliteCloudRepository(
            temp_db,
            secret_store=SecretStore(tmp_path / "secret.key"),
        )
        account_id = repo.add_account(sample_account)

        result = repo.update_account_token(
            account_id,
            access_token="updated_access",
            refresh_token="updated_refresh",
        )

        assert result is True
        account = repo.get_account_by_id(account_id)
        assert account.access_token == "updated_access"
        assert account.refresh_token == "updated_refresh"

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT access_token, refresh_token FROM cloud_accounts WHERE id = ?",
            (account_id,),
        )
        raw_access_token, raw_refresh_token = cursor.fetchone()
        conn.close()

        assert raw_access_token != "updated_access"
        assert raw_refresh_token != "updated_refresh"

    def test_get_account_by_id_keeps_legacy_plaintext_tokens_compatible(self, temp_db, tmp_path):
        """Existing plaintext rows should remain readable during migration."""
        repo = SqliteCloudRepository(
            temp_db,
            secret_store=SecretStore(tmp_path / "secret.key"),
        )

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO cloud_accounts (
                provider, account_name, account_email, access_token, refresh_token
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("quark", "Legacy Account", "legacy@example.com", "legacy_access", "legacy_refresh"),
        )
        account_id = cursor.lastrowid
        conn.commit()
        conn.close()

        account = repo.get_account_by_id(account_id)

        assert account.access_token == "legacy_access"
        assert account.refresh_token == "legacy_refresh"

    def test_update_account_token(self, cloud_repo, sample_account):
        """Test updating account tokens (both access and refresh)."""
        account_id = cloud_repo.add_account(sample_account)

        result = cloud_repo.update_account_token(
            account_id, access_token="new_access", refresh_token="new_refresh"
        )
        assert result is True

        account = cloud_repo.get_account_by_id(account_id)
        assert account.access_token == "new_access"
        assert account.refresh_token == "new_refresh"

    def test_update_account_token_access_only(self, cloud_repo, sample_account):
        """Test updating only access token."""
        account_id = cloud_repo.add_account(sample_account)

        result = cloud_repo.update_account_token(account_id, access_token="new_access")
        assert result is True

        account = cloud_repo.get_account_by_id(account_id)
        assert account.access_token == "new_access"
        # Refresh token should remain unchanged
        assert account.refresh_token == "refresh123"

    def test_update_account_token_nonexistent(self, cloud_repo):
        """Test updating token for non-existent account."""
        result = cloud_repo.update_account_token(99999, access_token="token")
        assert result is False

    def test_update_account_folder(self, cloud_repo, sample_account):
        """Test updating account folder path."""
        account_id = cloud_repo.add_account(sample_account)

        result = cloud_repo.update_account_folder(
            account_id, folder_id="folder_123",
            folder_path="/Music/Album", fid_path="0/fid1/fid2"
        )
        assert result is True

        account = cloud_repo.get_account_by_id(account_id)
        assert account.last_folder_path == "/Music/Album"
        assert account.last_fid_path == "0/fid1/fid2"

    def test_update_account_folder_nonexistent(self, cloud_repo):
        """Test updating folder for non-existent account."""
        result = cloud_repo.update_account_folder(
            99999, folder_id="f1", folder_path="/path", fid_path="0"
        )
        assert result is False

    def test_update_account_playing_state_all_fields(self, cloud_repo, sample_account):
        """Test updating playing state with all fields."""
        account_id = cloud_repo.add_account(sample_account)

        result = cloud_repo.update_account_playing_state(
            account_id, playing_fid="fid_123",
            position=45.5, local_path="/cache/song.mp3"
        )
        assert result is True

        account = cloud_repo.get_account_by_id(account_id)
        assert account.last_playing_fid == "fid_123"
        assert account.last_position == 45.5
        assert account.last_playing_local_path == "/cache/song.mp3"

    def test_update_account_playing_state_fid_and_position(self, cloud_repo, sample_account):
        """Test updating playing state with fid and position only."""
        account_id = cloud_repo.add_account(sample_account)

        result = cloud_repo.update_account_playing_state(
            account_id, playing_fid="fid_456", position=120.0
        )
        assert result is True

        account = cloud_repo.get_account_by_id(account_id)
        assert account.last_playing_fid == "fid_456"
        assert account.last_position == 120.0

    def test_update_account_playing_state_fid_and_local_path(self, cloud_repo, sample_account):
        """Test updating playing state with fid and local_path only."""
        account_id = cloud_repo.add_account(sample_account)

        result = cloud_repo.update_account_playing_state(
            account_id, playing_fid="fid_789", local_path="/cache/other.mp3"
        )
        assert result is True

        account = cloud_repo.get_account_by_id(account_id)
        assert account.last_playing_fid == "fid_789"
        assert account.last_playing_local_path == "/cache/other.mp3"

    def test_update_account_playing_state_fid_only(self, cloud_repo, sample_account):
        """Test updating playing state with fid only."""
        account_id = cloud_repo.add_account(sample_account)

        result = cloud_repo.update_account_playing_state(
            account_id, playing_fid="fid_only"
        )
        assert result is True

        account = cloud_repo.get_account_by_id(account_id)
        assert account.last_playing_fid == "fid_only"

    def test_update_account_playing_state_position_only(self, cloud_repo, sample_account):
        """Test updating playing state with position only."""
        account_id = cloud_repo.add_account(sample_account)

        result = cloud_repo.update_account_playing_state(account_id, position=99.9)
        assert result is True

        account = cloud_repo.get_account_by_id(account_id)
        assert account.last_position == 99.9

    def test_update_account_playing_state_local_path_only(self, cloud_repo, sample_account):
        """Test updating playing state with local_path only."""
        account_id = cloud_repo.add_account(sample_account)

        result = cloud_repo.update_account_playing_state(account_id, local_path="/only/path.mp3")
        assert result is True

        account = cloud_repo.get_account_by_id(account_id)
        assert account.last_playing_local_path == "/only/path.mp3"

    def test_update_account_playing_state_no_params(self, cloud_repo, sample_account):
        """Test updating playing state with no parameters does nothing."""
        account_id = cloud_repo.add_account(sample_account)

        result = cloud_repo.update_account_playing_state(account_id)
        assert result is False


class TestCloudFileSpecializedQueries:
    """Test specialized cloud file query operations."""

    def test_get_file_by_local_path(self, cloud_repo, sample_account, sample_file):
        """Test getting file by local path."""
        account_id = cloud_repo.add_account(sample_account)
        sample_file.account_id = account_id
        sample_file.local_path = "/downloads/song.mp3"
        cloud_repo.add_file(sample_file)

        retrieved = cloud_repo.get_file_by_local_path("/downloads/song.mp3")
        assert retrieved is not None
        assert retrieved.name == "test_song.mp3"
        assert retrieved.account_id == account_id

    def test_get_file_by_local_path_not_found(self, cloud_repo):
        """Test getting file by non-existent local path."""
        retrieved = cloud_repo.get_file_by_local_path("/nonexistent/path.mp3")
        assert retrieved is None

    def test_get_file_by_file_id_alias(self, cloud_repo, sample_account, sample_file):
        """Test get_file_by_file_id alias works same as get_file_by_id."""
        account_id = cloud_repo.add_account(sample_account)
        sample_file.account_id = account_id
        cloud_repo.add_file(sample_file)

        retrieved = cloud_repo.get_file_by_file_id("file_12345")
        assert retrieved is not None
        assert retrieved.name == "test_song.mp3"

    def test_get_files_by_parent(self, cloud_repo, sample_account):
        """Test getting files by parent folder ID."""
        account_id = cloud_repo.add_account(sample_account)

        file1 = CloudFile(
            account_id=account_id, file_id="f1", parent_id="folder_A",
            name="song1.mp3", file_type="audio"
        )
        file2 = CloudFile(
            account_id=account_id, file_id="f2", parent_id="folder_A",
            name="song2.mp3", file_type="audio"
        )
        file3 = CloudFile(
            account_id=account_id, file_id="f3", parent_id="folder_B",
            name="song3.mp3", file_type="audio"
        )
        cloud_repo.add_file(file1)
        cloud_repo.add_file(file2)
        cloud_repo.add_file(file3)

        folder_a_files = cloud_repo.get_files_by_parent(account_id, "folder_A")
        assert len(folder_a_files) == 2
        names = {f.name for f in folder_a_files}
        assert names == {"song1.mp3", "song2.mp3"}

        folder_b_files = cloud_repo.get_files_by_parent(account_id, "folder_B")
        assert len(folder_b_files) == 1
        assert folder_b_files[0].name == "song3.mp3"

    def test_get_files_by_parent_empty(self, cloud_repo, sample_account):
        """Test getting files by parent when no files exist."""
        account_id = cloud_repo.add_account(sample_account)
        files = cloud_repo.get_files_by_parent(account_id, "nonexistent")
        assert files == []

    def test_get_all_downloaded(self, cloud_repo, sample_account):
        """Test getting all files that have been downloaded."""
        account_id = cloud_repo.add_account(sample_account)

        # File with local path (downloaded)
        downloaded = CloudFile(
            account_id=account_id, file_id="d1", name="downloaded.mp3",
            file_type="audio", local_path="/cache/d1.mp3"
        )
        # File without local path (not downloaded)
        not_downloaded = CloudFile(
            account_id=account_id, file_id="nd1", name="remote.mp3",
            file_type="audio"
        )
        cloud_repo.add_file(downloaded)
        cloud_repo.add_file(not_downloaded)

        all_downloaded = cloud_repo.get_all_downloaded()
        assert len(all_downloaded) == 1
        assert all_downloaded[0].file_id == "d1"

    def test_get_all_downloaded_empty(self, cloud_repo):
        """Test getting all downloaded when none exist."""
        result = cloud_repo.get_all_downloaded()
        assert result == []

    def test_get_all_downloaded_empty_local_path_excluded(self, cloud_repo, sample_account):
        """Test that files with empty string local_path are excluded."""
        account_id = cloud_repo.add_account(sample_account)

        empty_local = CloudFile(
            account_id=account_id, file_id="e1", name="empty.mp3",
            file_type="audio", local_path=""
        )
        cloud_repo.add_file(empty_local)

        all_downloaded = cloud_repo.get_all_downloaded()
        assert len(all_downloaded) == 0

    def test_cache_files_preserves_local_path(self, cloud_repo, sample_account):
        """Test that cache_files preserves existing local_path."""
        account_id = cloud_repo.add_account(sample_account)

        # Add a file with local_path
        existing_file = CloudFile(
            account_id=account_id, file_id="f1", parent_id="folder_A",
            name="song.mp3", file_type="audio", local_path="/cache/song.mp3"
        )
        cloud_repo.add_file(existing_file)

        # Cache new files for same folder - same file_id but updated metadata
        new_files = [
            CloudFile(
                account_id=account_id, file_id="f1", parent_id="folder_A",
                name="song.mp3", file_type="audio", size=9999999
            ),
            CloudFile(
                account_id=account_id, file_id="f2", parent_id="folder_A",
                name="new.mp3", file_type="audio"
            ),
        ]

        result = cloud_repo.cache_files(account_id, new_files)
        assert result is True

        # Verify local_path is preserved for existing file
        f1 = cloud_repo.get_file_by_id("f1")
        assert f1.local_path == "/cache/song.mp3"

        # Verify new file has no local_path
        f2 = cloud_repo.get_file_by_id("f2")
        assert f2.local_path is None

        # Only files in the specific folder should be present
        all_files = cloud_repo.get_files_by_parent(account_id, "folder_A")
        assert len(all_files) == 2

    def test_cache_files_empty_list(self, cloud_repo):
        """Test that caching empty file list returns True."""
        result = cloud_repo.cache_files(1, [])
        assert result is True

    def test_cache_files_empty_listing_clears_existing_folder(self, cloud_repo, sample_account):
        """Explicit empty folder refresh should clear cached rows for that folder."""
        account_id = cloud_repo.add_account(sample_account)
        cloud_repo.add_file(
            CloudFile(
                account_id=account_id,
                file_id="stale1",
                parent_id="folder_A",
                name="stale.mp3",
                file_type="audio",
            )
        )

        result = cloud_repo.cache_files(account_id, [], parent_id="folder_A")

        assert result is True
        assert cloud_repo.get_files_by_parent(account_id, "folder_A") == []

    def test_cache_files_deletes_old_folder(self, cloud_repo, sample_account):
        """Test that cache_files deletes old files for the same folder only."""
        account_id = cloud_repo.add_account(sample_account)

        # Add files in two different folders
        old_folder_file = CloudFile(
            account_id=account_id, file_id="old1", parent_id="folder_A",
            name="old.mp3", file_type="audio"
        )
        other_folder_file = CloudFile(
            account_id=account_id, file_id="other1", parent_id="folder_B",
            name="other.mp3", file_type="audio"
        )
        cloud_repo.add_file(old_folder_file)
        cloud_repo.add_file(other_folder_file)

        # Cache new files for folder_A only
        new_files = [
            CloudFile(
                account_id=account_id, file_id="new1", parent_id="folder_A",
                name="new.mp3", file_type="audio"
            ),
        ]
        cloud_repo.cache_files(account_id, new_files)

        # folder_A should only have new file
        folder_a_files = cloud_repo.get_files_by_parent(account_id, "folder_A")
        assert len(folder_a_files) == 1
        assert folder_a_files[0].file_id == "new1"

        # folder_B should be untouched
        folder_b_files = cloud_repo.get_files_by_parent(account_id, "folder_B")
        assert len(folder_b_files) == 1
        assert folder_b_files[0].file_id == "other1"

    def test_get_file_by_id_and_account(self, cloud_repo, sample_account, sample_file):
        """Test getting file by ID and account."""
        account_id = cloud_repo.add_account(sample_account)
        sample_file.account_id = account_id
        cloud_repo.add_file(sample_file)

        retrieved = cloud_repo.get_file("file_12345", account_id)
        assert retrieved is not None
        assert retrieved.name == "test_song.mp3"

    def test_get_file_wrong_account(self, cloud_repo, sample_account, sample_file):
        """Test getting file with wrong account returns None."""
        account_id = cloud_repo.add_account(sample_account)
        sample_file.account_id = account_id
        cloud_repo.add_file(sample_file)

        retrieved = cloud_repo.get_file("file_12345", 99999)
        assert retrieved is None

    def test_update_file_local_path(self, cloud_repo, sample_account, sample_file):
        """Test updating local path for a file by account."""
        account_id = cloud_repo.add_account(sample_account)
        sample_file.account_id = account_id
        cloud_repo.add_file(sample_file)

        result = cloud_repo.update_file_local_path(
            "file_12345", account_id, "/new/local/path.mp3"
        )
        assert result is True

        file = cloud_repo.get_file_by_id("file_12345")
        assert file.local_path == "/new/local/path.mp3"

    def test_update_file_local_path_wrong_account(self, cloud_repo, sample_account, sample_file):
        """Test updating local path with wrong account fails."""
        account_id = cloud_repo.add_account(sample_account)
        sample_file.account_id = account_id
        cloud_repo.add_file(sample_file)

        result = cloud_repo.update_file_local_path(
            "file_12345", 99999, "/path.mp3"
        )
        assert result is False

    def test_hard_delete_account_removes_account(self, cloud_repo, sample_account):
        """Test that hard delete actually removes the account row."""
        account_id = cloud_repo.add_account(sample_account)

        result = cloud_repo.hard_delete_account(account_id)
        assert result is True

        # Account should be completely gone (not soft deleted)
        retrieved = cloud_repo.get_account_by_id(account_id)
        assert retrieved is None

    def test_hard_delete_account_nonexistent(self, cloud_repo):
        """Test hard deleting non-existent account returns False."""
        result = cloud_repo.hard_delete_account(99999)
        assert result is False

    def test_hard_delete_account_nonexistent_does_not_delete_orphan_files(self, temp_db):
        """Hard delete should not remove orphan files when account row is absent."""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO cloud_files (account_id, file_id, name, file_type)
            VALUES (?, ?, ?, ?)
            """,
            (99999, "orphan-file", "orphan.mp3", "audio"),
        )
        conn.commit()
        conn.close()

        repo = SqliteCloudRepository(temp_db)

        result = repo.hard_delete_account(99999)

        assert result is False
        assert repo.get_file_by_id("orphan-file") is not None
