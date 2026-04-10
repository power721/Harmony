# Optimization Report Wave D Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the UI, utility, domain-model, and service-composition items from the report while preserving visible behavior and keeping each report item in its own commit.

**Architecture:** This wave groups work that changes view-layer behavior, reusable UI helpers, utility performance, and domain semantics. UI refactors should introduce reusable helpers only when they directly remove duplication named in the report, and domain changes should preserve repository compatibility.

**Tech Stack:** Python 3.11+, PySide6, pytest, uv, git

---

## File Map

- Modify: `ui/windows/mini_player.py`
- Modify: `ui/windows/now_playing_window.py`
- Modify: `ui/windows/main_window.py`
- Modify: `ui/windows/components/scan_dialog.py`
- Modify: `ui/views/albums_view.py`
- Modify: `ui/views/artists_view.py`
- Modify: `ui/views/library_view.py`
- Modify: `ui/views/album_view.py`
- Modify: `ui/widgets/album_card.py`
- Modify: `ui/widgets/artist_card.py`
- Modify: `ui/widgets/equalizer_widget.py`
- Modify: `ui/icons.py`
- Modify: `ui/dialogs/base_rename_dialog.py`
- Modify: `ui/dialogs/edit_media_info_dialog.py`
- Modify: `ui/dialogs/lyrics_download_dialog.py`
- Modify: `utils/helpers.py`
- Modify: `utils/match_scorer.py`
- Modify: `utils/dedup.py`
- Modify: `utils/file_helpers.py`
- Modify: `utils/lrc_parser.py`
- Modify: `domain/album.py`
- Modify: `domain/artist.py`
- Modify: `domain/genre.py`
- Modify: `domain/playlist_item.py`
- Modify: `domain/online_music.py`
- Modify: `services/ai/acoustid_service.py`
- Test: `tests/test_ui/test_mini_player_thread_cleanup.py`
- Test: `tests/test_ui/test_now_playing_window_thread_cleanup.py`
- Test: `tests/test_ui/test_albums_view_thread_cleanup.py`
- Test: `tests/test_ui/test_artists_view_thread_cleanup.py`
- Test: `tests/test_ui/test_library_view.py`
- Test: `tests/test_ui/test_equalizer_widget.py`
- Test: `tests/test_ui/test_scan_dialog_cleanup.py`
- Test: `tests/test_ui/test_scan_dialog_architecture.py`
- Test: `tests/test_utils/test_helpers.py`
- Test: `tests/test_utils/test_match_scorer.py`
- Test: `tests/test_utils/test_dedup.py`
- Test: `tests/test_utils/test_file_helpers.py`
- Test: `tests/test_domain/test_album.py`
- Test: `tests/test_domain/test_artist.py`
- Test: `tests/test_domain/test_genre_id.py`
- Test: `tests/test_domain/test_playlist_item.py`
- Test: `tests/test_domain/test_online_music.py`

### Task 1: UI Signal Cleanup, Thread Pools, And Shutdown Flow

**Files:**
- Modify: `ui/windows/mini_player.py`
- Modify: `ui/windows/now_playing_window.py`
- Modify: `ui/views/albums_view.py`
- Modify: `ui/views/artists_view.py`
- Modify: `ui/views/library_view.py`
- Modify: `ui/dialogs/lyrics_download_dialog.py`
- Modify: `app/bootstrap.py`
- Test: `tests/test_ui/test_mini_player_thread_cleanup.py`
- Test: `tests/test_ui/test_now_playing_window_thread_cleanup.py`
- Test: `tests/test_ui/test_albums_view_thread_cleanup.py`
- Test: `tests/test_ui/test_artists_view_thread_cleanup.py`
- Test: `tests/test_ui/test_library_view.py`

- [ ] **Step 1: Add coverage for report items 4.4, 4.9, and 4.10**

```python
def test_window_close_disconnects_player_signals(...): ...
def test_view_cleanup_waits_for_executor_shutdown(...): ...
def test_bootstrap_flushes_repositories_before_db_shutdown(...): ...
```

- [ ] **Step 2: Run the focused UI and app tests**

Run:
- `uv run pytest tests/test_ui/test_mini_player_thread_cleanup.py -v`
- `uv run pytest tests/test_ui/test_now_playing_window_thread_cleanup.py -v`
- `uv run pytest tests/test_ui/test_albums_view_thread_cleanup.py -v`
- `uv run pytest tests/test_ui/test_artists_view_thread_cleanup.py -v`
- `uv run pytest tests/test_ui/test_library_view.py -v`

Expected: FAIL where signal disconnection, executor shutdown, or bootstrap flushing is missing.

- [ ] **Step 3: Implement the cleanup changes**

```python
def closeEvent(self, event):
    self._disconnect_player_signals()
    super().closeEvent(event)

def cleanup(self):
    self._executor.shutdown(wait=True)

def shutdown_database(self):
    self._flush_pending_repository_writes()
    self._db_manager.shutdown_database()
```

- [ ] **Step 4: Re-run the focused tests**

Run:
- `uv run pytest tests/test_ui/test_mini_player_thread_cleanup.py -v`
- `uv run pytest tests/test_ui/test_now_playing_window_thread_cleanup.py -v`
- `uv run pytest tests/test_ui/test_albums_view_thread_cleanup.py -v`
- `uv run pytest tests/test_ui/test_artists_view_thread_cleanup.py -v`
- `uv run pytest tests/test_ui/test_library_view.py -v`

Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add ui/windows/mini_player.py ui/windows/now_playing_window.py ui/views/albums_view.py ui/views/artists_view.py ui/views/library_view.py ui/dialogs/lyrics_download_dialog.py tests/test_ui/test_mini_player_thread_cleanup.py tests/test_ui/test_now_playing_window_thread_cleanup.py tests/test_ui/test_albums_view_thread_cleanup.py tests/test_ui/test_artists_view_thread_cleanup.py tests/test_ui/test_library_view.py
git commit -m "优化 4.4 界面信号连接清理"

git add ui/views/albums_view.py ui/views/artists_view.py ui/widgets/album_card.py tests/test_ui/test_albums_view_thread_cleanup.py tests/test_ui/test_artists_view_thread_cleanup.py
git commit -m "优化 4.9 线程池生命周期"

git add app/bootstrap.py tests/test_ui/test_library_view.py
git commit -m "优化 4.10 启动关闭流程"
```

### Task 2: Utility Performance And Cleanup

**Files:**
- Modify: `utils/helpers.py`
- Modify: `utils/match_scorer.py`
- Modify: `utils/dedup.py`
- Modify: `utils/file_helpers.py`
- Modify: `utils/lrc_parser.py`
- Test: `tests/test_utils/test_helpers.py`
- Test: `tests/test_utils/test_match_scorer.py`
- Test: `tests/test_utils/test_dedup.py`
- Test: `tests/test_utils/test_file_helpers.py`

- [ ] **Step 1: Add coverage for report items 3.8, 3.9, 3.13, 6.6, 6.7, 6.8, and 10.5**

```python
def test_find_lyric_line_uses_bisect_contract(...): ...
def test_match_scorer_combined_pattern_preserves_normalization(...): ...
def test_dedup_combined_patterns_preserve_existing_matches(...): ...
def test_helpers_uses_file_helpers_sanitize_filename(...): ...
def test_format_relative_time_uses_local_timezone(...): ...
```

- [ ] **Step 2: Run the focused utility tests**

Run:
- `uv run pytest tests/test_utils/test_helpers.py -v`
- `uv run pytest tests/test_utils/test_match_scorer.py -v`
- `uv run pytest tests/test_utils/test_dedup.py -v`
- `uv run pytest tests/test_utils/test_file_helpers.py -v`

Expected: FAIL where bisect, regex consolidation, or timezone handling is not yet implemented.

- [ ] **Step 3: Implement the utility changes**

```python
index = bisect.bisect_right(timestamps, current_time) - 1
_COMBINED_NORMALIZER = re.compile(pattern_a + "|" + pattern_b + "|...")
from utils.file_helpers import sanitize_filename
```

- [ ] **Step 4: Re-run the focused utility tests**

Run:
- `uv run pytest tests/test_utils/test_helpers.py -v`
- `uv run pytest tests/test_utils/test_match_scorer.py -v`
- `uv run pytest tests/test_utils/test_dedup.py -v`
- `uv run pytest tests/test_utils/test_file_helpers.py -v`

Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add utils/helpers.py tests/test_utils/test_helpers.py
git commit -m "优化 3.8 歌词行查找"

git add utils/match_scorer.py tests/test_utils/test_match_scorer.py
git commit -m "优化 3.9 匹配评分正则"

git add utils/dedup.py tests/test_utils/test_dedup.py
git commit -m "优化 3.13 去重正则编译"

git add utils/helpers.py utils/file_helpers.py tests/test_utils/test_helpers.py tests/test_utils/test_file_helpers.py
git commit -m "优化 6.6 文件名清理包装"

git add infrastructure/audio/audio_engine.py system/config.py utils/lrc_parser.py
git commit -m "优化 6.7 冗余导入"

git add utils/file_helpers.py system/hotkeys.py utils/dedup.py
git commit -m "优化 6.8 未使用代码清理"

git add utils/helpers.py tests/test_utils/test_helpers.py
git commit -m "优化 10.5 相对时间时区"
```

### Task 3: UI Responsiveness And Rendering

**Files:**
- Modify: `ui/dialogs/base_rename_dialog.py`
- Modify: `ui/dialogs/edit_media_info_dialog.py`
- Modify: `ui/widgets/equalizer_widget.py`
- Modify: `ui/views/album_view.py`
- Modify: `ui/windows/main_window.py`
- Modify: `ui/widgets/artist_card.py`
- Modify: `ui/icons.py`
- Test: `tests/test_ui/test_equalizer_widget.py`
- Test: `tests/test_ui/test_main_window_components.py`
- Test: `tests/test_ui/test_scan_dialog_architecture.py`

- [ ] **Step 1: Add coverage for report items 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, and 8.8**

```python
def test_resize_mask_application_is_debounced(...): ...
def test_edit_dialog_loads_mutagen_work_off_main_thread(...): ...
def test_equalizer_reuses_tracked_controls_on_theme_refresh(...): ...
def test_default_cover_pixmap_is_cached(...): ...
def test_icon_cache_uses_tuple_key(...): ...
```

- [ ] **Step 2: Run the focused UI tests**

Run:
- `uv run pytest tests/test_ui/test_equalizer_widget.py -v`
- `uv run pytest tests/test_ui/test_main_window_components.py -v`
- `uv run pytest tests/test_ui/test_scan_dialog_architecture.py -v`

Expected: FAIL where debounce, off-thread loading, or cache reuse is missing.

- [ ] **Step 3: Implement the rendering and responsiveness changes**

```python
self._resize_timer = QTimer(self)
self._resize_timer.setSingleShot(True)
self._resize_timer.start(100)

QTimer.singleShot(0, self.refresh_theme)

cache_key = (icon_name, color, size)
```

- [ ] **Step 4: Re-run the focused UI tests**

Run:
- `uv run pytest tests/test_ui/test_equalizer_widget.py -v`
- `uv run pytest tests/test_ui/test_main_window_components.py -v`
- `uv run pytest tests/test_ui/test_scan_dialog_architecture.py -v`

Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add ui/dialogs/base_rename_dialog.py
git commit -m "优化 8.1 对话框遮罩刷新"

git add ui/dialogs/edit_media_info_dialog.py tests/test_ui/test_scan_dialog_architecture.py
git commit -m "优化 8.2 媒体信息读取线程"

git add ui/dialogs/base_rename_dialog.py ui/views/library_view.py ui/windows/mini_player.py ui/windows/now_playing_window.py
git commit -m "优化 8.3 主题样式刷新"

git add ui/widgets/equalizer_widget.py tests/test_ui/test_equalizer_widget.py
git commit -m "优化 8.4 均衡器主题刷新"

git add ui/widgets/artist_card.py
git commit -m "优化 8.5 Pixmap双重缩放"

git add ui/views/album_view.py
git commit -m "优化 8.6 默认封面缓存"

git add ui/windows/main_window.py tests/test_ui/test_main_window_components.py
git commit -m "优化 8.7 主题刷新时机"

git add ui/icons.py
git commit -m "优化 8.8 图标缓存键"
```

### Task 4: Reusable UI Helpers And Error Handling

**Files:**
- Modify: `ui/dialogs/add_to_playlist_dialog.py`
- Modify: `ui/dialogs/base_rename_dialog.py`
- Modify: `ui/dialogs/message_dialog.py`
- Modify: `ui/windows/mini_player.py`
- Modify: `ui/windows/now_playing_window.py`
- Modify: `ui/widgets/album_card.py`
- Modify: `ui/widgets/artist_card.py`
- Modify: `ui/windows/components/scan_dialog.py`
- Test: `tests/test_ui/test_scan_dialog_cleanup.py`
- Test: `tests/test_ui/test_mini_player_cover_worker.py`

- [ ] **Step 1: Add coverage for report items 5.6, 6.3, 6.4, and 6.5**

```python
def test_scan_worker_counts_metadata_failures_without_crashing(...): ...
def test_dialogs_share_drag_mixin_behavior(...): ...
def test_cover_loader_reuses_common_loading_rules(...): ...
def test_artist_and_album_cards_share_hover_effect_logic(...): ...
```

- [ ] **Step 2: Run the focused UI tests**

Run:
- `uv run pytest tests/test_ui/test_scan_dialog_cleanup.py -v`
- `uv run pytest tests/test_ui/test_mini_player_cover_worker.py -v`

Expected: FAIL where error handling or duplicated helper extraction is not in place.

- [ ] **Step 3: Implement the helper extraction and error handling**

```python
class DraggableDialogMixin: ...
class CoverLoader(QObject): ...
class HoverEffectMixin: ...

try:
    metadata = metadata_service.extract_metadata(path)
except Exception:
    self.failed_count += 1
```

- [ ] **Step 4: Re-run the focused UI tests**

Run:
- `uv run pytest tests/test_ui/test_scan_dialog_cleanup.py -v`
- `uv run pytest tests/test_ui/test_mini_player_cover_worker.py -v`

Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add ui/windows/components/scan_dialog.py tests/test_ui/test_scan_dialog_cleanup.py
git commit -m "优化 5.6 扫描元数据错误处理"

git add ui/dialogs/add_to_playlist_dialog.py ui/dialogs/base_rename_dialog.py ui/dialogs/message_dialog.py
git commit -m "优化 6.3 对话框拖拽复用"

git add ui/windows/mini_player.py ui/windows/now_playing_window.py ui/widgets/album_card.py tests/test_ui/test_mini_player_cover_worker.py
git commit -m "优化 6.4 封面加载复用"

git add ui/widgets/album_card.py ui/widgets/artist_card.py
git commit -m "优化 6.5 悬停效果复用"
```

### Task 5: Domain And Service Composition Consistency

**Files:**
- Modify: `domain/album.py`
- Modify: `domain/artist.py`
- Modify: `domain/genre.py`
- Modify: `domain/playlist_item.py`
- Modify: `domain/online_music.py`
- Modify: `services/ai/acoustid_service.py`
- Test: `tests/test_domain/test_album.py`
- Test: `tests/test_domain/test_artist.py`
- Test: `tests/test_domain/test_genre_id.py`
- Test: `tests/test_domain/test_playlist_item.py`
- Test: `tests/test_domain/test_online_music.py`

- [ ] **Step 1: Add coverage for report items 9.1, 9.2, 9.3, 9.4, 9.5, and 10.2**

```python
def test_domain_dataclasses_use_slots(...): ...
def test_album_artist_genre_id_contract_is_consistent(...): ...
def test_search_type_is_enum(...): ...
def test_playlist_item_mutation_contract_is_explicit(...): ...
def test_acoustid_service_uses_injected_metadata_service(...): ...
def test_playlist_item_factory_validates_inputs(...): ...
```

- [ ] **Step 2: Run the focused domain tests**

Run:
- `uv run pytest tests/test_domain/test_album.py -v`
- `uv run pytest tests/test_domain/test_artist.py -v`
- `uv run pytest tests/test_domain/test_genre_id.py -v`
- `uv run pytest tests/test_domain/test_playlist_item.py -v`
- `uv run pytest tests/test_domain/test_online_music.py -v`

Expected: FAIL where slots, enum conversion, or factory validation is absent.

- [ ] **Step 3: Implement the domain and service changes**

```python
@dataclass(slots=True)
class Album: ...

class SearchType(str, Enum):
    SONG = "song"

def from_track(cls, track: Track | None):
    if track is None:
        raise ValueError("track is required")
```

- [ ] **Step 4: Re-run the focused domain tests**

Run:
- `uv run pytest tests/test_domain/test_album.py -v`
- `uv run pytest tests/test_domain/test_artist.py -v`
- `uv run pytest tests/test_domain/test_genre_id.py -v`
- `uv run pytest tests/test_domain/test_playlist_item.py -v`
- `uv run pytest tests/test_domain/test_online_music.py -v`

Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add domain/album.py domain/artist.py domain/genre.py tests/test_domain/test_album.py tests/test_domain/test_artist.py tests/test_domain/test_genre_id.py
git commit -m "优化 9.1 领域模型slots"

git add domain/album.py domain/artist.py domain/genre.py tests/test_domain/test_album.py tests/test_domain/test_artist.py tests/test_domain/test_genre_id.py
git commit -m "优化 9.2 领域模型ID一致性"

git add domain/online_music.py tests/test_domain/test_online_music.py
git commit -m "优化 9.3 搜索类型枚举"

git add domain/playlist_item.py tests/test_domain/test_playlist_item.py
git commit -m "优化 9.4 播放列表项语义"

git add services/ai/acoustid_service.py
git commit -m "优化 9.5 声纹服务依赖注入"

git add domain/playlist_item.py tests/test_domain/test_playlist_item.py
git commit -m "优化 10.2 领域工厂校验"
```
