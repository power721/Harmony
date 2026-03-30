# Harmony Optimization Report

> Generated: 2026-03-30
> Scope: Full codebase audit of all Python source files

---

## Summary

| Category               | Count |
|------------------------|-------|
| Database / N+1 Queries | 12    |
| Regex Pre-compilation  | 8     |
| Algorithm Improvement  | 6     |
| Batch Operations       | 7     |
| Caching                | 10    |
| Code Duplication       | 12    |
| UI Responsiveness      | 8     |
| Memory                 | 5     |
| I/O / Network          | 8     |
| Architecture           | 4     |
| **Total**              | **80**|

---

## 1. Database / N+1 Queries

### OPT-D01: N+1 Query in Track Artist Insertion

- **File**: `repositories/track_repository.py`
- **Lines**: 117-135, 752-768, 812-820
- **Priority**: Critical

For each artist, two separate queries are executed inside a loop — an INSERT and a SELECT:

```python
for position, artist_name in enumerate(artist_names):
    cursor.execute("INSERT INTO artists (name, ...) VALUES (?, ?) ON CONFLICT ...", ...)
    cursor.execute("SELECT id FROM artists WHERE name = ?", (artist_name,))  # N+1
    artist_row = cursor.fetchone()
```

**Fix**: Use `cursor.lastrowid` after INSERT, or use `INSERT ... RETURNING id`.

---

### OPT-D02: Individual Track Lookups in Loops

- **Files**: `services/playback/playback_service.py` (lines 437-443), `services/playback/handlers.py` (lines 134-140), `services/library/file_organization_service.py` (lines 80-85)
- **Priority**: Critical

```python
for track_id in track_ids:
    track = self._db.get_track(track_id)  # 1 query per track
```

**Fix**: Add `get_tracks_by_ids(ids)` batch method using `WHERE id IN (...)`, reducing N queries to 1.

---

### OPT-D03: Individual Cloud File Lookups in play_cloud_playlist

- **File**: `services/playback/playback_service.py`
- **Lines**: 627-654
- **Priority**: High

```python
for i, cf in enumerate(cloud_files):
    track = self._db.get_track_by_cloud_file_id(cf.file_id)  # 1 query per file
```

**Fix**: Batch-load all tracks: `get_tracks_by_cloud_file_ids(file_ids)` with a single `WHERE cloud_file_id IN (...)`.

---

### OPT-D04: Individual Metadata Enrichment in Queue Restore

- **Files**: `services/playback/queue_service.py` (line 75), `services/playback/playback_service.py` (line 849)
- **Priority**: High

```python
items = [self._enrich_metadata(item) for item in items]  # Each does a DB lookup
```

**Fix**: Pre-load all track IDs in one batch, build a `{id: track}` dict, then enrich in memory.

---

### OPT-D05: Separate Cover Path Query

- **Files**: `repositories/album_repository.py` (lines 147-161), `repositories/artist_repository.py` (lines 124-131)
- **Priority**: Medium

Two queries per album/artist: one for aggregated data, one for cover path.

**Fix**: Combine into a single query with subquery:
```sql
SELECT ..., (SELECT cover_path FROM tracks t2
  WHERE t2.album = t.album AND t2.cover_path IS NOT NULL LIMIT 1) as cover_path
FROM tracks t WHERE ...
```

---

### OPT-D06: Redundant `SELECT 1 FROM table LIMIT 1` Cache Checks

- **Files**: `repositories/album_repository.py` (lines 35, 95), `repositories/artist_repository.py` (lines 35, 93)
- **Priority**: Medium

Called on every `get_all` / `get_by_name`. The result is always the same until a refresh.

**Fix**: Cache the boolean result at initialization; invalidate on refresh.

---

### OPT-D07: Redundant Artist Normalization Queries

- **File**: `repositories/track_repository.py`
- **Lines**: 102-104, 745-746
- **Priority**: Medium

```python
cursor.execute("SELECT normalized_name FROM artists")
known_artists = {row[0] for row in cursor.fetchall()}  # Called multiple times
```

**Fix**: Load once at startup and cache in memory. Invalidate on artist table changes.

---

### OPT-D08: Individual INSERTs in Cloud File Cache

- **File**: `repositories/cloud_repository.py`
- **Lines**: 400-446
- **Priority**: Medium

```python
for file in files:
    cursor.execute("INSERT INTO cloud_files ...", ...)
```

**Fix**: Use `cursor.executemany()` for batch insert.

---

### OPT-D09: Individual INSERTs in add_tracks_bulk

- **File**: `infrastructure/database/sqlite_manager.py`
- **Lines**: 1126-1208
- **Priority**: High

Despite the name "bulk", tracks are inserted one at a time with individual `SELECT` existence checks.

**Fix**: Use `INSERT OR REPLACE` with `executemany`, or batch the existence checks with `WHERE path IN (...)`.

---

### OPT-D10: Missing Composite Indexes

- **File**: `infrastructure/database/sqlite_manager.py`
- **Lines**: 318-326
- **Priority**: Medium

Common queries on `(album, artist)`, `(track_id, played_at)`, `(path, id)` lack composite indexes.

**Fix**: Add targeted indexes:
```sql
CREATE INDEX IF NOT EXISTS idx_tracks_album_artist ON tracks(album, artist);
CREATE INDEX IF NOT EXISTS idx_history_track_played ON play_history(track_id, played_at);
```

---

### OPT-D11: Inefficient Schema Migration Check

- **File**: `infrastructure/database/sqlite_manager.py`
- **Lines**: 675-951
- **Priority**: Low

All migrations run `PRAGMA table_info` checks on every startup, regardless of schema version.

**Fix**: Gate migration blocks by `stored_version < migration_version` and increment `CURRENT_SCHEMA_VERSION` to match migration count.

---

### OPT-D12: Playlist Position Calculated with Extra Query

- **File**: `infrastructure/database/sqlite_manager.py`
- **Lines**: 1608-1616
- **Priority**: Low

Separate `SELECT MAX(position)` before INSERT.

**Fix**: Inline into INSERT: `INSERT INTO playlist_items (..., position) SELECT ..., COALESCE(MAX(position),-1)+1 FROM playlist_items WHERE playlist_id=?`.

---

## 2. Regex Pre-compilation

### OPT-R01: file_helpers.py — 3 patterns compiled on every call

- **File**: `utils/file_helpers.py`
- **Lines**: 26, 28, 30
- **Priority**: High

```python
cleaned = re.sub(r'[\\/]', '&', name)
cleaned = re.sub(r'[<>:"|?*]', '', cleaned)
cleaned = re.sub(r'\s+', ' ', cleaned).strip('. ')
```

**Fix**: Pre-compile at module level: `_RE_PATH_SEP = re.compile(r'[\\/]')` etc.

---

### OPT-R02: helpers.py — 3 patterns compiled on every call

- **File**: `utils/helpers.py`
- **Lines**: 167, 176, 178
- **Priority**: High

`parse_filename_as_metadata()` compiles `r'^(.+?)\s*-\s*(.+)$'`, `r'\[[^\]]+\]'`, `r'\([^)]*\)'` every time.

**Fix**: Pre-compile at module level.

---

### OPT-R03: online/adapter.py — 30+ inline `re.sub()` calls

- **File**: `services/online/adapter.py`
- **Lines**: 111, 123, 130, 135, 141, 149, 155, 160, ...
- **Priority**: High

HTML tag removal regex like `re.sub(r'<[^>]+>', '', text)` appears 30+ times.

**Fix**: Pre-compile `_RE_HTML_TAG = re.compile(r'<[^>]+>')` at module level.

---

### OPT-R04: artist_parser.py — patterns in split loop

- **File**: `services/metadata/artist_parser.py`
- **Lines**: 59-62
- **Priority**: Medium

```python
if re.match(r'^[\s,，、/\\&]+$', part, re.IGNORECASE): continue
if re.match(r'^(feat\.?|featuring|ft\.?|and)$', part, re.IGNORECASE): continue
```

**Fix**: Pre-compile both patterns.

---

### OPT-R05: baidu_service.py — re imported inside loop

- **File**: `services/cloud/baidu_service.py`
- **Lines**: 177, 182
- **Priority**: Medium

```python
import re
match = re.search(r'BDUSS=([^;]+)', set_cookie)
```

**Fix**: Remove redundant imports; pre-compile patterns at module level.

---

### OPT-R06: qr_login.py — 6+ inline regex calls

- **File**: `services/cloud/qqmusic/qr_login.py`
- **Lines**: 237, 306, 318-319, 346, 414, 446
- **Priority**: Medium

**Fix**: Pre-compile at class level.

---

### OPT-R07: ai_metadata_service.py — repeated JSON extraction regex

- **File**: `services/ai/ai_metadata_service.py`
- **Lines**: 111-149, 341-380
- **Priority**: Medium

Multiple `re.search()` calls for JSON block extraction.

**Fix**: Pre-compile `_RE_JSON_BLOCK = re.compile(r'```(?:json)?\s*([\s\S]*?)\s*```')` etc.

---

### OPT-R08: match_scorer.py — duplicate bracket/paren patterns

- **File**: `utils/match_scorer.py`
- **Lines**: 81-98
- **Priority**: Low

Separate patterns for `()` and `[]` variants of the same content (e.g., `(mv)` and `[mv]`).

**Fix**: Combine using character classes: `r'\s*[\(\[]mv[\)\]]'` — reduces 18 patterns to ~9.

---

## 3. Algorithm Improvements

### OPT-A01: Linear Search for Cloud Files — O(n) per lookup

- **Files**: `services/playback/playback_service.py` (lines 1206-1209), `services/playback/handlers.py` (lines 489-492)
- **Priority**: High

```python
for cf in self._cloud_files:
    if cf.file_id == item.cloud_file_id:
        cloud_file = cf
        break
```

**Fix**: Build `_cloud_files_by_id = {cf.file_id: cf for cf in self._cloud_files}` — O(1) lookup.

---

### OPT-A02: Linear Search for Playlist Items by cloud_file_id

- **File**: `services/playback/playback_service.py`
- **Lines**: 688-693
- **Priority**: Medium

```python
for item in self._engine.playlist_items:
    if item.cloud_file_id == cloud_file_id: ...
```

**Fix**: Maintain an index dict `{cloud_file_id: item}` on playlist load.

---

### OPT-A03: Extension check uses list instead of set

- **File**: `utils/helpers.py`
- **Lines**: 199-202
- **Priority**: Medium

```python
extensions = ['.mp3', '.flac', '.m4a', '.wav', '.ogg', '.wma', '.ape', '.aac']
if any(title_lower.endswith(ext) for ext in extensions): ...
```

**Fix**: Use `frozenset` at module level. Also consider extracting the suffix with `os.path.splitext` for O(1).

---

### OPT-A04: Artist parser uses O(n^2) nested loops

- **File**: `services/metadata/artist_parser.py`
- **Lines**: 117-155
- **Priority**: Medium

```python
for j in range(i + 1, len(parts) + 1):
    candidate = ' '.join(parts[i:j])
    if normalize_artist_name(candidate) in known_artists: ...
```

**Fix**: Use a trie or prefix-set for O(n) matching.

---

### OPT-A05: Chinese character detection iterates all chars

- **File**: `services/ai/acoustid_service.py`
- **Lines**: 121-126
- **Priority**: Low

```python
return any(char in cls.TRADITIONAL_CHARS for char in text)
```

**Fix**: Use `bool(set(text) & cls.TRADITIONAL_CHARS)` for O(min(m,n)) via set intersection.

---

### OPT-A06: QQMusic quality fallback uses repeated `.index()`

- **File**: `services/cloud/qqmusic/client.py`
- **Lines**: 405-409
- **Priority**: Low

```python
for q in APIConfig.QUALITY_FALLBACK:
    if APIConfig.QUALITY_FALLBACK.index(q) < APIConfig.QUALITY_FALLBACK.index(quality):
        continue
```

**Fix**: Pre-compute start index with `enumerate()`.

---

## 4. Batch Operations

### OPT-B01: Repeated File Existence Checks

- **Files**: `services/playback/playback_service.py` (7 locations), `services/playback/handlers.py` (7 locations)
- **Priority**: High

`Path(track.path).exists()` is called per track inside loops.

**Fix**: Pre-compute `existing_paths = {p for p in all_paths if Path(p).exists()}` before the loop.

---

### OPT-B02: Album/Artist Refresh Runs Immediately — No Debounce

- **File**: `services/library/library_service.py`
- **Lines**: 128-139
- **Priority**: High

```python
# Actually refresh immediately for now (TODO: add debouncing)
self._album_repo.refresh()
self._artist_repo.refresh()
```

**Fix**: Implement debounce with `QTimer.singleShot(500, self._do_refresh)`.

---

### OPT-B03: Batch Edit Dialog Saves Metadata Sequentially

- **File**: `ui/dialogs/edit_media_info_dialog.py`
- **Lines**: 470-510
- **Priority**: Medium

Saves metadata for each track one at a time on the UI thread.

**Fix**: Move to a background worker thread; batch the DB updates.

---

### OPT-B04: Lyrics Search Rebuilds Entire List on Each Source Completion

- **File**: `ui/dialogs/lyrics_download_dialog.py`
- **Lines**: 304-335
- **Priority**: Medium

```python
self._song_list.clear()  # Clears and re-adds all items
for result in unique_results:
    self._song_list.addItem(...)
```

**Fix**: Track existing IDs in a set; only insert new items incrementally.

---

### OPT-B05: Multiple Sequential Cover Fetch Attempts

- **File**: `services/playback/playback_service.py`
- **Lines**: 1602-1671
- **Priority**: Medium

Cover sources tried sequentially (QQ Music, Spotify, etc.).

**Fix**: Use `ThreadPoolExecutor` to query sources concurrently.

---

### OPT-B06: Lyrics Encoding Detection Tries Up to 18 Opens

- **File**: `services/lyrics/lyrics_service.py`
- **Lines**: 324-340
- **Priority**: Medium

Tries 6 encodings x 3 file extensions in worst case.

**Fix**: Use `chardet` to detect encoding from a small sample first, then read once.

---

### OPT-B07: Old Lyrics Cleanup Pattern Repeated 3 Times

- **File**: `services/lyrics/lyrics_service.py`
- **Lines**: 460-466, 496-500, 524-527
- **Priority**: Low

```python
for ext in ['.lrc', '.yrc', '.qrc']:
    old_path = track_file.with_suffix(ext)
    if old_path.exists(): old_path.unlink()
```

**Fix**: Extract to `_cleanup_old_lyrics_files(track_path)`.

---

## 5. Caching

### OPT-C01: Favorite Track IDs Not Cached

- **File**: `services/library/favorites_service.py`
- **Lines**: 54-61
- **Priority**: High

`get_all_favorite_track_ids()` hits the DB on every call; UI may call it frequently.

**Fix**: Cache in-memory with invalidation on add/remove.

---

### OPT-C02: Dedup Extracts Version Info Twice Per Track

- **File**: `utils/dedup.py`
- **Lines**: 254, 315
- **Priority**: Medium

`extract_version_info(title)` called in `get_track_key()` and again in dedup scoring loop.

**Fix**: Cache results in a `{title: VersionInfo}` dict within `deduplicate_playlist_items`.

---

### OPT-C03: Cover Service Re-filters Sources on Every Call

- **File**: `services/metadata/cover_service.py`
- **Lines**: 43-58
- **Priority**: Medium

```python
def _get_sources(self):
    if self._sources is None:
        self._sources = [...]
    return [s for s in self._sources if s.is_available()]  # Filters every call
```

**Fix**: Cache available sources; refresh only when credentials change.

---

### OPT-C04: Lyrics Sources Recreated on Each Operation

- **File**: `services/lyrics/lyrics_service.py`
- **Lines**: 57-71
- **Priority**: Medium

`_get_sources()` creates new source instances each time it's called.

**Fix**: Cache at class level with lazy initialization.

---

### OPT-C05: Cover Cache Key Uses Non-deterministic `hash()`

- **File**: `services/metadata/cover_service.py`
- **Lines**: 148, 189
- **Priority**: High

```python
cache_filename = f"{track_file.stem}_{hash(track_path)}.jpg"
```

Python's `hash()` is randomized across runs — cache files become unreachable after restart.

**Fix**: Use `hashlib.md5(track_path.encode()).hexdigest()[:16]`.

---

### OPT-C06: Spotify Token Not Shared Across Sources

- **Files**: `services/sources/cover_sources.py`, `services/sources/artist_cover_sources.py`
- **Priority**: Medium

Each source class independently fetches and caches a Spotify access token.

**Fix**: Share a single `SpotifyTokenManager` singleton.

---

### OPT-C07: Cloud File Service Has No In-Memory Cache

- **File**: `services/cloud/cloud_file_service.py`
- **Lines**: 36-47
- **Priority**: Low

Direct pass-through to repository on every call.

**Fix**: Add simple TTL cache for recently accessed folders.

---

### OPT-C08: QQMusic Credential Check on Every API Call

- **File**: `services/online/online_music_service.py`
- **Lines**: 51-63
- **Priority**: Low

`_has_qqmusic_credential()` checks config on every call.

**Fix**: Cache result with short TTL (e.g., 30s).

---

### OPT-C09: Online Cache Cleaner Calls glob/stat Repeatedly

- **File**: `services/online/cache_cleaner_service.py`
- **Lines**: 179-181, 278-279
- **Priority**: Low

Multiple `glob()` and `stat()` calls on the same directory.

**Fix**: Cache file list and stat results within a single cleanup pass.

---

### OPT-C10: find_current_line Rebuilds Times List Every Call

- **File**: `utils/lrc_parser.py`
- **Lines**: 348-361
- **Priority**: Medium

```python
def find_current_line(lines, t):
    times = [line.time for line in lines]  # Rebuilt every call
    i = bisect.bisect_right(times, t) - 1
```

Called ~10 times/sec during playback.

**Fix**: Pre-build the times list once when lyrics are loaded; pass it as a parameter or store alongside lines.

---

## 6. Code Duplication / Simplification

### OPT-S01: Track Loading Logic Duplicated 6+ Times

- **Files**: `services/playback/playback_service.py`, `services/playback/handlers.py`
- **Priority**: Critical

`play_local_track()`, `play_local_tracks()`, `play_local_library()`, `load_playlist()`, `play_playlist_track()`, `load_favorites()` all contain near-identical filter-convert-load logic.

**Fix**: Extract `_filter_and_convert_tracks(tracks) -> List[PlaylistItem]`.

---

### OPT-S02: Save-to-Library Logic Duplicated Across 3 Handlers

- **Files**: `services/playback/playback_service.py` (lines 1304-1358, 1443-1600), `services/playback/handlers.py` (lines 555-664)
- **Priority**: High

Near-identical metadata extraction, existing-track check, and Track creation.

**Fix**: Consolidate into `_save_downloaded_track_to_library(local_path, source, metadata)`.

---

### OPT-S03: Shuffle-and-Play Pattern Repeated 8+ Times

- **Files**: `services/playback/playback_service.py`, `services/playback/handlers.py`
- **Priority**: Medium

```python
if self._engine.is_shuffle_mode() and 0 <= start_index < len(items):
    self._engine.shuffle_and_play(items[start_index])
    self._engine.play_at(0)
else:
    self._engine.play_at(start_index)
```

**Fix**: Extract to `_play_with_shuffle_support(items, start_index)`.

---

### OPT-S04: Cover File Lookup Pattern Repeated 3+ Times

- **File**: `services/metadata/cover_service.py`
- **Lines**: 213-216, 462-465, 488-491
- **Priority**: Medium

```python
for ext in ['.jpg', '.jpeg', '.png']:
    cover_path = self.CACHE_DIR / f"{cache_key}{ext}"
    if cover_path.exists(): return cover_path
```

**Fix**: Extract to `_find_cached_cover(cache_key)`.

---

### OPT-S05: Parallel Search Pattern Repeated 3 Times

- **File**: `services/metadata/cover_service.py`
- **Lines**: 304-329, 371-394, 527-545
- **Priority**: Medium

Identical `ThreadPoolExecutor` + `as_completed` boilerplate.

**Fix**: Extract to `_parallel_search(sources, search_fn, timeout)`.

---

### OPT-S06: AlbumRenameDialog / ArtistRenameDialog Nearly Identical

- **Files**: `ui/dialogs/album_rename_dialog.py`, `ui/dialogs/artist_rename_dialog.py`
- **Priority**: Medium

Both inherit from `BaseRenameDialog` but still have significant duplication.

**Fix**: Parameterize the differences further or use a single configurable dialog.

---

### OPT-S07: Singer Info Extraction Duplicated in QQMusic Lyrics

- **File**: `services/lyrics/qqmusic_lyrics.py`
- **Lines**: 172-189, 234-253
- **Priority**: Low

Identical singer/album extraction logic in local and remote search methods.

**Fix**: Extract `_extract_singer_info(song_data)`.

---

### OPT-S08: JSON Parsing Logic Duplicated in AI Service

- **File**: `services/ai/ai_metadata_service.py`
- **Lines**: 111-149, 341-380
- **Priority**: Low

`_parse_json_response()` and `_parse_batch_json_response()` share identical fallback chain.

**Fix**: Extract `_extract_json_from_text(content)`.

---

### OPT-S09: Dialog Shadow Setup Copied Across All Dialogs

- **Files**: Multiple `ui/dialogs/*.py`
- **Priority**: Low

Every dialog has identical `_setup_shadow()` method.

**Fix**: Create shared `setup_dialog_shadow(widget)` utility.

---

### OPT-S10: Cloud Services Duplicate Header Construction

- **Files**: `services/cloud/quark_service.py` (3 locations), `services/cloud/baidu_service.py` (7 locations)
- **Priority**: Low

HTTP headers rebuilt inline for each method.

**Fix**: Create class-level header template property.

---

### OPT-S11: Row-to-Object Conversion Duplicated

- **Files**: Multiple repositories, `infrastructure/database/sqlite_manager.py` (line 1550-1582)
- **Priority**: Low

Inline `Track(id=row["id"], ...)` instead of using existing `_row_to_track` helper.

**Fix**: Use the helper consistently.

---

### OPT-S12: Theme `to_dict()` Manual Instead of `asdict()`

- **File**: `system/theme.py`
- **Lines**: 35-49
- **Priority**: Low

**Fix**: Replace with `from dataclasses import asdict; return asdict(self)`.

---

## 7. UI Responsiveness

### OPT-U01: Table Population Without `setUpdatesEnabled(False)`

- **Files**: `ui/views/library_view.py` (lines 509-620), `ui/views/playlist_view.py` (lines 534-575)
- **Priority**: High

Tables populated row-by-row without disabling updates, causing repaints per row.

**Fix**: Wrap with `table.setUpdatesEnabled(False)` ... `table.setUpdatesEnabled(True)`.

---

### OPT-U02: Cover Preloading Logic Runs Inside `paint()`

- **File**: `ui/views/queue_view.py`
- **Lines**: 416-433
- **Priority**: High

The delegate's `paint()` method spawns background workers for nearby covers.

**Fix**: Move preloading to scroll event handler; `paint()` should only draw.

---

### OPT-U03: Position Timer Always Running

- **File**: `ui/widgets/player_controls.py`
- **Lines**: 197-200
- **Priority**: Medium

Timer fires every 100ms even when paused.

**Fix**: Start timer on play, stop on pause/stop.

---

### OPT-U04: Massive Stylesheet Reconstruction in `refresh_theme()`

- **Files**: `ui/views/artist_view.py` (226 lines), `ui/views/albums_view.py`, `ui/views/artists_view.py`
- **Priority**: High

Entire stylesheet trees rebuilt with f-string interpolation on every theme change.

**Fix**: Use template token replacement at the `ThemeManager` level; cache the result per template hash.

---

### OPT-U05: `findChildren()` / `findChild()` Used in Theme Refresh

- **Files**: `ui/views/artist_view.py` (14 calls), `ui/widgets/equalizer_widget.py`, `ui/dialogs/help_dialog.py`
- **Priority**: Medium

`findChildren(QLabel)` is O(n) tree traversal, repeated per theme change.

**Fix**: Store widget references during `_setup_ui()`.

---

### OPT-U06: ThreadPoolExecutor Created Per Cover Download

- **File**: `ui/views/online_grid_view.py`
- **Lines**: 177-227
- **Priority**: High

```python
executor = ThreadPoolExecutor(max_workers=1)
future = executor.submit(download)
```

New executor per download, plus polling with `QTimer.singleShot(100, check_download)`.

**Fix**: Use class-level `QThreadPool` or shared executor; replace polling with signal/callback.

---

### OPT-U07: Circular Mask Recreated Per Cover Load

- **File**: `ui/views/online_grid_view.py`
- **Lines**: 245-258
- **Priority**: Medium

Creates a circular QPixmap mask every time a singer cover is loaded.

**Fix**: Create mask once as class constant; reuse via composition mode.

---

### OPT-U08: Settings Dialog Initializes All Tabs Eagerly

- **File**: `ui/dialogs/settings_dialog.py`
- **Lines**: 208-524
- **Priority**: Low

All tabs (AI, AcoustID, QQ Music, Cache, etc.) built upfront.

**Fix**: Lazy-load tab content on `currentChanged` signal.

---

## 8. Memory

### OPT-M01: Missing `__slots__` on Lyric Dataclasses

- **File**: `utils/lrc_parser.py`
- **Lines**: 13-34
- **Priority**: Medium

`LyricWord` and `LyricLine` can have thousands of instances per song.

**Fix**: Add `__slots__` to both classes (~40% memory reduction per instance).

---

### OPT-M02: Default Cover Pixmap Recreated Every Time

- **File**: `ui/views/album_view.py`
- **Lines**: 558-575
- **Priority**: Medium

`_set_default_cover()` creates a new 200x200 QPixmap each call.

**Fix**: Create once as class-level constant.

---

### OPT-M03: Duplicate Traditional Chinese Character Set

- **File**: `services/ai/acoustid_service.py`
- **Lines**: 21-112
- **Priority**: Low

~90 lines of character data with many duplicates.

**Fix**: Deduplicate the set literal.

---

### OPT-M04: Intermediate List in Generator

- **File**: `utils/dedup.py`
- **Lines**: 334-335
- **Priority**: Low

```python
return sorted([w for l in lines for w in l.words], key=lambda w: w.time)
```

**Fix**: Use generator: `sorted((w for l in lines for w in l.words), key=...)`.

---

### OPT-M05: Color Extractor Converts Image Format Unconditionally

- **File**: `services/metadata/color_extractor.py`
- **Lines**: 32-35
- **Priority**: Low

```python
converted = image.convertToFormat(QImage.Format_RGB32)
```

**Fix**: Check format first: `if image.format() != QImage.Format_RGB32:`.

---

## 9. I/O / Network

### OPT-N01: Cloud Services Missing `requests.Session` Reuse

- **Files**: `services/cloud/quark_service.py` (7 call sites), `services/cloud/baidu_service.py` (9 call sites)
- **Priority**: High

Every API call creates a new TCP connection.

**Fix**: Use a class-level `requests.Session()` for connection pooling.

---

### OPT-N02: QQMusic Lyrics Creates New Session Per Request

- **File**: `services/lyrics/qqmusic_lyrics.py`
- **Lines**: 226, 311, 371, 441
- **Priority**: High

```python
session = requests.Session()  # New session per method call
```

**Fix**: Reuse `self.session` created in `__init__`.

---

### OPT-N03: Cover/Lyrics Sources Missing Session Reuse

- **Files**: `services/sources/cover_sources.py` (9 call sites), `services/sources/lyrics_sources.py` (7 call sites), `services/sources/artist_cover_sources.py` (4 call sites)
- **Priority**: Medium

**Fix**: Use `HttpClient` session or class-level `requests.Session()`.

---

### OPT-N04: HttpClient Missing Connection Pooling Config

- **File**: `infrastructure/network/http_client.py`
- **Lines**: 17-30
- **Priority**: Medium

Session created but no adapter with pool configuration.

**Fix**: Mount `HTTPAdapter(pool_connections=10, pool_maxsize=10)`.

---

### OPT-N05: Full Metadata Extraction Just for Cover

- **File**: `services/metadata/metadata_service.py`
- **Lines**: 254-276
- **Priority**: Medium

`save_cover()` calls `extract_metadata()` which parses title/artist/album just to get cover bytes.

**Fix**: Create `_extract_cover_only()` that reads only APIC/cover frames.

---

### OPT-N06: Inconsistent Timeout Values in Cloud Services

- **File**: `services/cloud/quark_service.py`
- **Lines**: multiple (10s, 30s, 60s)
- **Priority**: Low

**Fix**: Define timeout constants at class level.

---

### OPT-N07: Online Download Missing Retry Logic

- **Files**: `services/download/download_manager.py`, `services/online/download_service.py`
- **Priority**: Medium

Downloads fail silently without retry.

**Fix**: Implement exponential backoff retry (e.g., 3 attempts).

---

### OPT-N08: Download Chunk Size Hard-coded at 8KB

- **Files**: `services/cloud/download_service.py` (line 154), `services/online/download_service.py` (line 188)
- **Priority**: Low

**Fix**: Use adaptive chunk size (e.g., 64KB for files >10MB).

---

## 10. Architecture

### OPT-X01: MainWindow is God Object (1751 lines)

- **File**: `ui/windows/main_window.py`
- **Priority**: High

Manages playback, UI state, dialogs, lyrics, online music, sidebar, theme, hotkeys, tray icon.

**Fix**: Extract into focused controllers:
  - `PlaybackController` — playback logic
  - `DialogFactory` — dialog creation
  - `UIStateManager` — view/navigation state

---

### OPT-X02: DBWriteWorker.stop() Never Called

- **File**: `infrastructure/database/db_write_worker.py`, `app/application.py`
- **Priority**: High

No shutdown hook for the database write worker.

**Fix**: Call `write_worker.wait_idle()` then `write_worker.stop()` in `Application.quit()`.

---

### OPT-X03: Direct DB Access Bypasses Write Worker

- **Files**: `services/playback/playback_service.py` (line 1528), `services/library/file_organization_service.py` (line 196)
- **Priority**: High

Code directly calls `self._db._get_connection()` to execute raw SQL, bypassing the serialized write worker.

**Fix**: Use proper `DatabaseManager` methods through the write worker.

---

### OPT-X04: Missing Unified Stylesheet Caching System

- **Files**: All views and dialogs with `_STYLE_TEMPLATE`
- **Priority**: Medium

Each widget independently calls `ThemeManager.get_qss(template)` and rebuilds stylesheets.

**Fix**: Implement a centralized `ThemeStyleCache` that pre-generates and caches all stylesheets on theme change, keyed by template hash.

---

## Priority Matrix

### Immediate (High Impact, Low Effort)

| ID | Description | Est. Lines Changed |
|----|-------------|-------------------|
| OPT-R01-R03 | Pre-compile regex patterns | ~30 |
| OPT-A01 | Cloud file dict lookup | ~10 |
| OPT-C05 | Fix hash() non-determinism | ~5 |
| OPT-U03 | Conditional position timer | ~10 |
| OPT-N02 | Reuse QQMusic session | ~10 |

### Short-term (High Impact, Medium Effort)

| ID | Description | Est. Lines Changed |
|----|-------------|-------------------|
| OPT-D02-D04 | Batch DB lookups | ~100 |
| OPT-D09 | Batch insert in add_tracks_bulk | ~50 |
| OPT-S01 | Extract track loading helper | ~200 (net removal) |
| OPT-B02 | Debounce album/artist refresh | ~20 |
| OPT-U01 | setUpdatesEnabled on tables | ~10 |
| OPT-N01 | Session reuse in cloud services | ~40 |
| OPT-X02 | DB shutdown hook | ~10 |

### Long-term (High Impact, High Effort)

| ID | Description | Est. Lines Changed |
|----|-------------|-------------------|
| OPT-X01 | Decompose MainWindow | ~500+ |
| OPT-X04 | Unified stylesheet cache | ~200 |
| OPT-S02 | Consolidate save-to-library | ~150 (net removal) |
| OPT-D10 | Add composite indexes | ~10 SQL lines |

---

## Appendix: Files Audited

All `.py` files in the following directories were read and reviewed:

- `app/` (2 files)
- `domain/` (9 files)
- `infrastructure/` (7 files)
- `repositories/` (11 files)
- `services/` (28 files)
- `system/` (5 files)
- `ui/` (40 files)
- `utils/` (6 files)
- `main.py`