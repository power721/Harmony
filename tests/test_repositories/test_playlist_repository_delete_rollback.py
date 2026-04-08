import sqlite3
from unittest.mock import Mock

from repositories.playlist_repository import SqlitePlaylistRepository


def test_delete_rolls_back_when_playlist_delete_fails():
    repo = SqlitePlaylistRepository.__new__(SqlitePlaylistRepository)
    cursor = Mock()
    cursor.execute.side_effect = [None, sqlite3.DatabaseError("boom")]
    conn = Mock(cursor=Mock(return_value=cursor))
    repo._get_connection = lambda: conn

    result = SqlitePlaylistRepository.delete(repo, 1)

    assert result is False
    conn.rollback.assert_called_once_with()
    conn.commit.assert_not_called()
