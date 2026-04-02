# Playback Queue Bugfixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the confirmed playback queue bugs around QQ cache reuse, empty-queue persistence, and duplicate online queue items.

**Architecture:** Keep the existing playback architecture intact and apply narrowly scoped fixes in the domain model, queue persistence services, and player engine indexing logic. The work is driven by regression tests first so each bug is fixed at its root without broad refactors.

**Tech Stack:** Python, pytest, PySide6, sqlite3

---

### Task 1: Preserve downloaded QQ local paths

**Files:**
- Modify: `domain/playlist_item.py`
- Modify: `services/playback/queue_service.py`
- Modify: `services/playback/playback_service.py`
- Test: `tests/test_domain/test_playlist_item.py`
- Test: `tests/test_services/test_queue_service.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_from_downloaded_online_track_preserves_local_path():
    track = Track(
        id=1,
        path="/tmp/cached.mp3",
        title="Downloaded",
        source=TrackSource.QQ,
        cloud_file_id="song_mid",
    )
    item = PlaylistItem.from_track(track)
    assert item.local_path == "/tmp/cached.mp3"
    assert item.needs_download is False


def test_enrich_metadata_batch_keeps_cached_qq_local_path(temp_dir):
    cached_path = temp_dir / "cached.mp3"
    cached_path.write_text("x")
    item = PlaylistItem(
        source=TrackSource.QQ,
        cloud_file_id="song_mid",
        local_path=str(cached_path),
        title="Downloaded",
        needs_download=False,
    )
    restored = queue_service._enrich_metadata_batch([item])[0]
    assert restored.local_path == str(cached_path)
    assert restored.needs_download is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_domain/test_playlist_item.py tests/test_services/test_queue_service.py -q`
Expected: FAIL on the new QQ cache assertions.

- [ ] **Step 3: Write minimal implementation**

```python
# domain/playlist_item.py
is_online = track.source == TrackSource.QQ and not track.path

if track.source == TrackSource.QQ and track.path:
    return cls(
        source=track.source,
        track_id=track.id,
        cloud_file_id=track.cloud_file_id,
        local_path=track.path,
        ...
        needs_download=False,
    )

# services/playback/queue_service.py / playback_service.py
# Include QQ paths in existence cache when a concrete local path exists.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_domain/test_playlist_item.py tests/test_services/test_queue_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_domain/test_playlist_item.py tests/test_services/test_queue_service.py domain/playlist_item.py services/playback/queue_service.py services/playback/playback_service.py
git commit -m "fix: preserve cached qq queue items"
```

### Task 2: Clear persisted state when the queue becomes empty

**Files:**
- Modify: `services/playback/queue_service.py`
- Modify: `services/playback/playback_service.py`
- Test: `tests/test_services/test_queue_service.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_save_clears_persisted_queue_when_engine_playlist_is_empty():
    repo.save([existing_item])
    engine.playlist_items = []
    queue_service.save()
    assert repo.count() == 0


def test_playback_service_save_queue_clears_repo_and_queue_config_when_empty():
    playback._engine.playlist_items = []
    playback.save_queue()
    assert queue_repo.count() == 0
    assert config.deleted_keys == {"queue_current_index", "queue_play_mode"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_services/test_queue_service.py -q`
Expected: FAIL because empty queues return early and leave stale persisted state.

- [ ] **Step 3: Write minimal implementation**

```python
def save(self):
    items = self._engine.playlist_items
    if not items:
        self.clear()
        return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_services/test_queue_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_services/test_queue_service.py services/playback/queue_service.py services/playback/playback_service.py
git commit -m "fix: clear persisted queue when empty"
```

### Task 3: Update duplicate online queue entries consistently

**Files:**
- Modify: `infrastructure/audio/audio_engine.py`
- Test: `tests/test_infrastructure/test_audio_engine.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_update_playlist_item_updates_all_duplicate_cloud_ids():
    engine.load_playlist_items([
        PlaylistItem(source=TrackSource.QQ, cloud_file_id="song_mid", needs_download=True),
        PlaylistItem(source=TrackSource.QQ, cloud_file_id="song_mid", needs_download=True),
    ])
    engine.update_playlist_item(cloud_file_id="song_mid", local_path="/tmp/a.mp3", needs_download=False)
    assert engine.playlist_items[0].local_path == "/tmp/a.mp3"
    assert engine.playlist_items[1].local_path == "/tmp/a.mp3"
    assert engine.playlist_items[1].needs_download is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_infrastructure/test_audio_engine.py -q`
Expected: FAIL because only the first indexed duplicate is updated.

- [ ] **Step 3: Write minimal implementation**

```python
def update_playlist_item(...):
    matched_indices = []
    if expected_index matches:
        matched_indices.append(expected_index)
    matched_indices.extend(
        i for i, item in enumerate(self._playlist)
        if item.cloud_file_id == cloud_file_id and i not in matched_indices
    )
    for i in matched_indices:
        ...
    return matched_indices[0] if matched_indices else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_infrastructure/test_audio_engine.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_infrastructure/test_audio_engine.py infrastructure/audio/audio_engine.py
git commit -m "fix: sync duplicate online queue entries"
```

### Task 4: Run focused regression suite

**Files:**
- Test: `tests/test_domain/test_playlist_item.py`
- Test: `tests/test_services/test_queue_service.py`
- Test: `tests/test_infrastructure/test_audio_engine.py`
- Test: `tests/test_repositories/test_queue_repository.py`

- [ ] **Step 1: Run the focused regression suite**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_domain/test_playlist_item.py tests/test_services/test_queue_service.py tests/test_infrastructure/test_audio_engine.py tests/test_repositories/test_queue_repository.py -q`
Expected: PASS

- [ ] **Step 2: Review the diff for accidental changes**

Run: `git diff -- domain/playlist_item.py infrastructure/audio/audio_engine.py services/playback/queue_service.py services/playback/playback_service.py tests/test_domain/test_playlist_item.py tests/test_services/test_queue_service.py tests/test_infrastructure/test_audio_engine.py`
Expected: Only the intended bugfix/test changes appear.

- [ ] **Step 3: Commit**

```bash
git add domain/playlist_item.py infrastructure/audio/audio_engine.py services/playback/queue_service.py services/playback/playback_service.py tests/test_domain/test_playlist_item.py tests/test_services/test_queue_service.py tests/test_infrastructure/test_audio_engine.py
git commit -m "fix: repair playback queue persistence edge cases"
```
