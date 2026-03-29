# Cloud Song Download Failure Handling - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mark cloud songs that fail to download as unplayable, auto-skip them during playback, show visual feedback in queue UI, and allow manual retry.

**Architecture:** Add `download_failed: bool` field to PlaylistItem and PlayQueueItem. PlaybackService marks items on download error. PlayerEngine auto-skips failed items. QueueItemDelegate renders them gray with label. Context menu adds retry action.

**Tech Stack:** Python, PySide6, SQLite

---

### Task 1: Add `download_failed` field to domain models

**Files:**
- Modify: `domain/playlist_item.py`
- Modify: `domain/playback.py`
- Test: `tests/test_domain/test_playlist_item.py`

- [ ] **Step 1: Write failing tests for `download_failed` field**

Add to `tests/test_domain/test_playlist_item.py`:

```python
def test_default_download_failed_is_false(self):
    """Test download_failed defaults to False."""
    item = PlaylistItem()
    assert item.download_failed is False

def test_is_ready_false_when_download_failed(self):
    """Test is_ready returns False when download_failed is True."""
    item = PlaylistItem(local_path="/music/song.mp3", needs_download=False, download_failed=True)
    assert item.is_ready is False

def test_is_ready_true_when_not_failed(self):
    """Test is_ready returns True when download_failed is False."""
    item = PlaylistItem(local_path="/music/song.mp3", needs_download=False, download_failed=False)
    assert item.is_ready is True

def test_to_dict_includes_download_failed(self):
    """Test to_dict includes download_failed."""
    item = PlaylistItem(download_failed=True)
    data = item.to_dict()
    assert data.get("download_failed") is True

def test_from_dict_reads_download_failed(self):
    """Test from_dict reads download_failed."""
    data = {"path": "/music/song.mp3", "download_failed": True}
    item = PlaylistItem.from_dict(data)
    assert item.download_failed is True

def test_with_metadata_download_failed(self):
    """Test with_metadata can update download_failed."""
    item = PlaylistItem(download_failed=False)
    updated = item.with_metadata(download_failed=True)
    assert updated.download_failed is True
    assert item.download_failed is False

def test_to_play_queue_item_includes_download_failed(self):
    """Test to_play_queue_item includes download_failed."""
    item = PlaylistItem(download_failed=True)
    queue_item = item.to_play_queue_item(position=0)
    assert queue_item.download_failed is True

def test_from_play_queue_item_reads_download_failed(self):
    """Test from_play_queue_item reads download_failed."""
    from domain.playback import PlayQueueItem
    queue_item = PlayQueueItem(position=0, source="QUARK", download_failed=True)
    playlist_item = PlaylistItem.from_play_queue_item(queue_item)
    assert playlist_item.download_failed is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_domain/test_playlist_item.py -v -k "download_failed"`
Expected: FAIL (AttributeError: no attribute `download_failed`)

- [ ] **Step 3: Add `download_failed` field to `PlayQueueItem`**

In `domain/playback.py`, add field after `duration`:

```python
download_failed: bool = False
```

- [ ] **Step 4: Add `download_failed` field to `PlaylistItem`**

In `domain/playlist_item.py`:

1. Add field after `cloud_file_size`:
```python
download_failed: bool = False  # Whether download has failed
```

2. Update `is_ready` property:
```python
@property
def is_ready(self) -> bool:
    """Check if the item is ready for playback (has valid local path)."""
    return bool(self.local_path) and not self.needs_download and not self.download_failed
```

3. Update `to_dict` to include:
```python
"download_failed": self.download_failed,
```

4. Update `from_dict` to read:
```python
download_failed=data.get("download_failed", False),
```

5. Update `with_metadata` to accept and pass `download_failed` parameter:
```python
def with_metadata(
    self,
    cover_path: Optional[str] = None,
    title: Optional[str] = None,
    artist: Optional[str] = None,
    album: Optional[str] = None,
    duration: Optional[float] = None,
    local_path: Optional[str] = None,
    track_id: Optional[int] = None,
    needs_download: Optional[bool] = None,
    needs_metadata: Optional[bool] = None,
    download_failed: Optional[bool] = None,
) -> "PlaylistItem":
```

Add to return:
```python
download_failed=download_failed if download_failed is not None else self.download_failed,
```

6. Update `to_play_queue_item`:
```python
download_failed=self.download_failed,
```

7. Update `from_play_queue_item`:
```python
download_failed=item.download_failed,
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_domain/test_playlist_item.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add domain/playlist_item.py domain/playback.py tests/test_domain/test_playlist_item.py
git commit -m "feat: add download_failed field to PlaylistItem and PlayQueueItem"
```

---

### Task 2: Persist `download_failed` in database

**Files:**
- Modify: `infrastructure/database/sqlite_manager.py` (schema migration)
- Modify: `repositories/queue_repository.py`
- Test: `tests/test_repositories/test_queue_repository.py`

- [ ] **Step 1: Write failing test for download_failed persistence**

Add to `tests/test_repositories/test_queue_repository.py`:

```python
def test_save_and_load_with_download_failed(self):
    """Test saving and loading queue items with download_failed field."""
    items = [
        PlayQueueItem(
            position=0, source="Local", track_id=1,
            local_path="/music/song.mp3", title="Local Song",
        ),
        PlayQueueItem(
            position=1, source="QUARK", cloud_file_id="quark_123",
            cloud_account_id=1, local_path="", title="Cloud Song",
            download_failed=True,
        ),
    ]
    assert self.repo.save(items) is True

    loaded = self.repo.load()
    assert len(loaded) == 2
    assert loaded[0].download_failed is False
    assert loaded[1].download_failed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_repositories/test_queue_repository.py -v -k "download_failed"`
Expected: FAIL (column not found or default False not read)

- [ ] **Step 3: Add schema migration to sqlite_manager.py**

In the migration section of `_migrate_database` (find where existing play_queue migrations are), add:

```python
# Add download_failed column to play_queue
cursor.execute("PRAGMA table_info(play_queue)")
columns = {row[1] for row in cursor.fetchall()}
if "download_failed" not in columns:
    cursor.execute("ALTER TABLE play_queue ADD COLUMN download_failed INTEGER DEFAULT 0")
```

- [ ] **Step 4: Update queue_repository.py load() to read download_failed**

In the `PlayQueueItem()` constructor call inside `load()`, add:
```python
download_failed=bool(row.get("download_failed", 0)),
```

- [ ] **Step 5: Update queue_repository.py save() to write download_failed**

Update the INSERT statement and values to include `download_failed`:
```sql
INSERT INTO play_queue (position, source, track_id, cloud_file_id,
                        cloud_account_id, local_path, title, artist, album, duration, created_at,
                        download_failed)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

Values tuple add: `item.download_failed`

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_repositories/test_queue_repository.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add infrastructure/database/sqlite_manager.py repositories/queue_repository.py tests/test_repositories/test_queue_repository.py
git commit -m "feat: persist download_failed in play_queue table"
```

---

### Task 3: Mark download failures in PlaybackService

**Files:**
- Modify: `services/playback/playback_service.py`

- [ ] **Step 1: Update `on_online_track_downloaded` to mark failed instead of remove**

In `services/playback/playback_service.py`, find `on_online_track_downloaded` (around line 1164). Replace the failure handling block (lines 1172-1185) that calls `remove_playlist_item_by_cloud_id` with:

```python
# Handle download failure
if not local_path:
    logger.warning(f"[PlaybackService] Online track download failed: {song_mid}")
    # Mark as failed instead of removing
    self._engine.update_playlist_item(
        cloud_file_id=song_mid,
        needs_download=True,
        download_failed=True,
    )
    # Skip to next track if this was the current track
    current_item = self._engine.current_playlist_item
    if current_item and current_item.cloud_file_id == song_mid:
        logger.warning(f"[PlaybackService] Current track failed to download, skipping: {song_mid}")
        self._engine.play_next()
    self._schedule_save_queue()
    return
```

- [ ] **Step 2: Connect `download_error` EventBus signal to cloud download failure handler**

In `_connect_download_service_signals` (around line 136), after the existing signal connections, add:

```python
# Handle cloud download errors - mark item as failed
self._event_bus.download_error.connect(self._on_cloud_download_error)
```

- [ ] **Step 3: Add `_on_cloud_download_error` handler**

Add new method to PlaybackService:

```python
def _on_cloud_download_error(self, file_id: str, error_message: str):
    """Handle cloud file download error - mark item as failed and skip."""
    logger.warning(f"[PlaybackService] Cloud download failed: {file_id} - {error_message}")

    # Mark as failed in engine
    self._engine.update_playlist_item(
        cloud_file_id=file_id,
        needs_download=True,
        download_failed=True,
    )

    # Skip if this is the current track
    current_item = self._engine.current_playlist_item
    if current_item and current_item.cloud_file_id == file_id:
        self._engine.play_next()

    self._schedule_save_queue()
```

- [ ] **Step 4: Update `update_playlist_item` in audio_engine.py to accept `download_failed`**

In `infrastructure/audio/audio_engine.py`, find `update_playlist_item` method (around line 303). Add `download_failed: bool = False` parameter and apply it:

```python
def update_playlist_item(
    self,
    cloud_file_id: str,
    local_path: str = None,
    track_id: int = None,
    title: str = None,
    artist: str = None,
    album: str = None,
    duration: float = None,
    cover_path: str = None,
    needs_download: bool = False,
    needs_metadata: bool = False,
    download_failed: bool = False,
    expected_index: int = None
) -> Optional[int]:
```

In both update blocks (expected_index path and O(1) lookup path), add:
```python
item.download_failed = download_failed
```

- [ ] **Step 5: Auto-skip failed items in `play()` and `play_at()`**

In `infrastructure/audio/audio_engine.py`, in `play()` method (around line 440), update the download check:

```python
# Check if current track needs download or file doesn't exist
if item.download_failed:
    logger.info(f"[Engine] Skipping failed track: {item.title}")
    self.track_finished.emit()
    return
if item.needs_download or not item.local_path or not Path(item.local_path).exists():
    item.needs_download = True
    self.track_needs_download.emit(item)
    return
```

In `play_at()` (around line 478), same pattern:

```python
if item.download_failed:
    logger.info(f"[Engine] Skipping failed track at index {index}: {item.title}")
    return
if item.needs_download or not item.local_path or not Path(item.local_path).exists():
    item.needs_download = True
    item_copy = item
else:
    item_copy = None
```

- [ ] **Step 6: Commit**

```bash
git add services/playback/playback_service.py infrastructure/audio/audio_engine.py
git commit -m "feat: mark download failures and auto-skip failed tracks"
```

---

### Task 4: Queue UI visual feedback for failed items

**Files:**
- Modify: `ui/views/queue_view.py`
- Modify: `translations/zh.json`
- Modify: `translations/en.json`

- [ ] **Step 1: Add `download_failed` to queue track model data**

In `ui/views/queue_view.py`, in `QueueItemDelegate.paint()` (around line 270), after reading the track dict, check for download_failed:

```python
track = index.data(QueueTrackModel.TrackRole)
is_download_failed = False
if isinstance(track, dict):
    is_download_failed = track.get("download_failed", False)
```

- [ ] **Step 2: Gray out failed items in paint()**

In the text colors section (around line 308), add a branch before existing logic:

```python
# Text colors
if is_download_failed:
    text_color = QColor(128, 128, 128)
    secondary_color = QColor(160, 160, 160)
elif is_selected:
    text_color = QColor(theme.background)
    secondary_color = QColor(theme.background)
elif is_current:
    text_color = QColor(theme.highlight)
    secondary_color = QColor(theme.highlight)
else:
    text_color = QColor(theme.text)
    secondary_color = QColor(theme.text_secondary)
```

- [ ] **Step 3: Show "下载失败" label instead of duration**

In the duration section (around line 362), replace:

```python
# Duration / status label
from system.i18n import t as i18n_t
if is_download_failed:
    duration_text = i18n_t("download_failed")
    font.setPixelSize(10)
else:
    duration = track.get("duration", 0) if isinstance(track, dict) else 0
    from utils.helpers import format_duration
    duration_text = format_duration(duration)
    font.setPixelSize(12)
font.setBold(False)
painter.setFont(font)
painter.drawText(rect.right() - self._padding - 50, rect.top(), 50, rect.height(),
                 Qt.AlignVCenter | Qt.AlignRight, duration_text)
```

- [ ] **Step 4: Add i18n keys (if not already present)**

`download_failed` already exists in translations. Verify:

```bash
python -c "import json; print(json.load(open('translations/zh.json'))['download_failed'])"
python -c "import json; print(json.load(open('translations/en.json'))['download_failed'])"
```

If missing in `en.json`, add:
```json
"download_failed": "Download Failed"
```

Also add `retry_download` key:
- `zh.json`: `"retry_download": "🔄 重试下载"`
- `en.json`: `"retry_download": "🔄 Retry Download"`

- [ ] **Step 5: Commit**

```bash
git add ui/views/queue_view.py translations/zh.json translations/en.json
git commit -m "feat: show gray + label for failed downloads in queue"
```

---

### Task 5: Add retry download via context menu

**Files:**
- Modify: `ui/views/queue_view.py`

- [ ] **Step 1: Add "Retry Download" action to context menu**

In `_show_context_menu` (around line 1117), after checking the index is valid, check if the track is download_failed and add retry action:

```python
def _show_context_menu(self, pos):
    """Show context menu."""
    index = self._list_view.indexAt(pos)
    if not index.isValid():
        return

    track = index.data(QueueTrackModel.TrackRole)
    is_download_failed = isinstance(track, dict) and track.get("download_failed", False)

    menu = QMenu(self)
    from system.theme import ThemeManager
    menu.setStyleSheet(ThemeManager.instance().get_qss(self._CONTEXT_MENU_STYLE))

    if is_download_failed:
        retry_action = menu.addAction(t("retry_download"))
        retry_action.triggered.connect(self._retry_download_selected)
        menu.addSeparator()

    # Play action (disabled for failed items)
    play_action = menu.addAction(t("play_now"))
    if is_download_failed:
        play_action.setEnabled(False)
    else:
        play_action.triggered.connect(self._play_selected)

    menu.addSeparator()

    # Add to playlist action
    add_to_playlist_action = menu.addAction(t("add_to_playlist"))
    add_to_playlist_action.triggered.connect(self._add_selected_to_playlist)

    remove_action = menu.addAction(t("remove_from_queue"))
    remove_action.triggered.connect(self._remove_selected)

    menu.exec_(self._list_view.mapToGlobal(pos))
```

- [ ] **Step 2: Add `_retry_download_selected` method**

Add to `QueueView` class:

```python
def _retry_download_selected(self):
    """Retry download for selected failed track."""
    index = self._list_view.currentIndex()
    if not index.isValid():
        return

    track = index.data(QueueTrackModel.TrackRole)
    if not isinstance(track, dict) or not track.get("download_failed", False):
        return

    from system.event_bus import EventBus
    bus = EventBus.instance()
    bus.track_needs_download.emit(track)
```

- [ ] **Step 3: Handle retry in PlaybackService `_on_track_needs_download`**

In `services/playback/playback_service.py`, at the start of `_on_track_needs_download` (around line 1051), clear the failed state before downloading:

```python
def _on_track_needs_download(self, item: PlaylistItem):
    """Handle track that needs download."""
    # Clear download_failed state when retrying
    item.download_failed = False
    item.needs_download = True

    if item.source == TrackSource.QQ:
        self._download_online_track(item)
    else:
        self._download_cloud_track(item)
```

Note: the item here may be a dict (from EventBus signal in retry case) or a PlaylistItem. Adjust accordingly — if dict, use the engine to update:

```python
def _on_track_needs_download(self, item):
    """Handle track that needs download."""
    # Clear download_failed state when retrying
    if isinstance(item, dict):
        cloud_file_id = item.get("cloud_file_id")
        if cloud_file_id:
            self._engine.update_playlist_item(
                cloud_file_id=cloud_file_id,
                download_failed=False,
                needs_download=True,
            )
        source_str = item.get("source", "Local")
    else:
        item.download_failed = False
        item.needs_download = True
        source_str = item.source.value

    from domain.track import TrackSource
    try:
        source = TrackSource(source_str)
    except ValueError:
        source = TrackSource.LOCAL

    if source == TrackSource.QQ:
        self._download_online_track(item if hasattr(item, 'source') else PlaylistItem.from_dict(item))
    else:
        self._download_cloud_track(item if hasattr(item, 'source') else PlaylistItem.from_dict(item))
```

- [ ] **Step 4: Commit**

```bash
git add ui/views/queue_view.py services/playback/playback_service.py
git commit -m "feat: add retry download via queue context menu"
```

---

### Task 6: Run full test suite and verify

- [ ] **Step 1: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Fix any test failures**

- [ ] **Step 3: Commit if any fixes needed**

```bash
git add -A
git commit -m "fix: update tests for download_failed field"
```
