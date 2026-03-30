# Harmony 音乐播放器 — 缺失测试用例完整报告

## 总览

| 层级 | 源文件数 | 有测试的文件 | 无测试的文件 | 预估缺失测试数 |
|------|---------|-------------|-------------|---------------|
| **Domain** | 9 | 9 | 0 | ~30 |
| **Repositories** | 10 | 8 | **2** | ~65 |
| **Services** | 32 | 5 | **27** | ~350+ |
| **Infrastructure** | 7 | 2 | **5** | ~85+ |
| **System** | 5 | 2 | **3** | ~90+ |
| **Utils** | 6 | 5 | **1** | ~30 |
| **App** | 2 | 0 | **2** | ~25 |
| **合计** | **71** | **31** | **40** | **~675+** |

---

## 一、完全没有测试文件的模块 (40个文件)

### 优先级 P0 — 核心功能，必须优先补测试

| # | 源文件 | 说明 | 预估测试数 |
|---|--------|------|-----------|
| 1 | `services/playback/playback_service.py` | 播放服务（核心） | 30+ |
| 2 | `services/playback/handlers.py` | 播放处理器（Local/Cloud/Online） | 30+ |
| 3 | `services/playback/queue_service.py` | 队列持久化服务 | 10+ |
| 4 | `infrastructure/audio/audio_engine.py` | 音频引擎（QMediaPlayer封装） | 50+ |
| 5 | `system/config.py` | 配置管理器（60+ getter/setter） | 60+ |
| 6 | `infrastructure/database/sqlite_manager.py` | 数据库管理（建表/索引/FTS5） | 10+ |
| 7 | `infrastructure/database/db_write_worker.py` | 数据库写入线程 | 15+ |
| 8 | `repositories/settings_repository.py` | 设置仓库（CRUD） | 5+ |
| 9 | `app/bootstrap.py` | 依赖注入容器 | 15+ |

### 优先级 P1 — 重要业务功能

| # | 源文件 | 说明 | 预估测试数 |
|---|--------|------|-----------|
| 10 | `services/library/playlist_service.py` | 播放列表服务 | 10 |
| 11 | `services/library/favorites_service.py` | 收藏服务 | 8 |
| 12 | `services/library/play_history_service.py` | 播放历史服务 | 6 |
| 13 | `services/library/file_organization_service.py` | 文件整理服务 | 5 |
| 14 | `services/lyrics/lyrics_service.py` | 歌词服务 | 15+ |
| 15 | `services/lyrics/lyrics_loader.py` | 歌词加载线程 | 5 |
| 16 | `services/metadata/cover_service.py` | 封面服务 | 17 |
| 17 | `services/online/online_music_service.py` | 在线音乐服务 | 20 |
| 18 | `services/online/adapter.py` | API适配器（YGKing/QQ） | 14 |
| 19 | `services/online/download_service.py` | 在线下载服务 | 11 |
| 20 | `services/online/cache_cleaner_service.py` | 缓存清理服务 | 13 |
| 21 | `services/download/download_manager.py` | 下载管理器 | 8 |

### 优先级 P2 — 云服务/第三方集成

| # | 源文件 | 说明 | 预估测试数 |
|---|--------|------|-----------|
| 22 | `services/cloud/quark_service.py` | 夸克网盘服务 | 10+ |
| 23 | `services/cloud/baidu_service.py` | 百度网盘服务 | 10+ |
| 24 | `services/cloud/cloud_file_service.py` | 云文件服务 | 10+ |
| 25 | `services/cloud/cloud_account_service.py` | 云账号服务 | 10+ |
| 26 | `services/cloud/download_service.py` | 云下载服务 | 5+ |
| 27 | `services/cloud/qqmusic/qqmusic_service.py` | QQ音乐服务 | 15+ |
| 28 | `services/cloud/qqmusic/client.py` | QQ音乐客户端 | 10+ |
| 29 | `services/cloud/qqmusic/crypto.py` | QQ音乐加密 | 5+ |
| 30 | `services/cloud/qqmusic/tripledes.py` | 3DES加密 | 5+ |
| 31 | `services/lyrics/qqmusic_lyrics.py` | QQ音乐歌词 | 15+ |
| 32 | `services/ai/ai_metadata_service.py` | AI元数据增强 | 7 |
| 33 | `services/ai/acoustid_service.py` | 声纹识别服务 | 6 |

### 优先级 P3 — 辅助模块

| # | 源文件 | 说明 | 预估测试数 |
|---|--------|------|-----------|
| 34 | `services/sources/base.py` | 源基类/数据类 | 5 |
| 35 | `services/sources/cover_sources.py` | 封面搜索源（6个） | 18 |
| 36 | `services/sources/artist_cover_sources.py` | 歌手封面源（4个） | 12 |
| 37 | `services/sources/lyrics_sources.py` | 歌词搜索源（4个） | 12 |
| 38 | `system/i18n.py` | 国际化 | 11 |
| 39 | `system/hotkeys.py` | 全局快捷键 | 14 |
| 40 | `infrastructure/fonts/font_loader.py` | 字体加载��� | 8 |
| 41 | `utils/playlist_utils.py` | 播放列表工具 | 10 |
| 42 | `app/application.py` | 应用单例 | 8 |

---

## 二、已有测试但覆盖不全的模块

### Domain 层 — 缺失的具体测试用例

**`domain/cloud.py`** — 覆盖率 ~27%

- `CloudAccount.is_active` 默认值 / 设为 False
- `CloudAccount.last_folder_path` 默认 `"/"` / 自定义路径
- `CloudAccount.last_fid_path` 默认 `"0"` / 自定义
- `CloudAccount.last_playing_fid` 默认空串 / 设值
- `CloudAccount.last_position` 默认 0.0 / 设值
- `CloudAccount.last_playing_local_path` 默认空串 / 设值
- `CloudAccount.token_expires_at` 默认 None / 设时间
- `CloudAccount.refresh_token` 默认空串 / 设值
- `CloudFile.metadata` / `local_path` / `mime_type` / `size` / `duration` 字段测试
- 时间戳一致性 (`updated_at >= created_at`)

**`domain/track.py`** — 覆盖率 ~70%

- `Track.source` 默认 `TrackSource.LOCAL` / 设其他值
- `Track.cloud_file_id` 默认 None / 设值
- `Track.file_size` / `file_mtime` 默认值和设值
- `TrackSource` 枚举字符串值验证 (`LOCAL="Local"`, `QUARK="QUARK"`, etc.)

**`domain/album.py`** — 覆盖率 ~75%

- `Album.duration` / `year` / `cover_path` / `song_count` 字段
- 不同 metadata 下的相等性

**`domain/playback.py`** — 覆盖率 ~75%

- `PlayQueueItem.download_failed` 默认 False / 设 True
- `PlayMode` / `PlaybackState` 枚举迭代和计数

**`domain/history.py`** — 覆盖率 ~67%

- `PlayHistory.id` / `Favorite.id` 默认值
- `play_count` 边界值（负数/零/极大值）

**`domain/playlist_item.py`** — 覆盖率 ~93%

- `from_cloud_file()` 小写 provider
- `from_dict()` 旧 `"path"` 字段兼容 / 无效 source 回退
- `with_metadata()` 保留 cloud 字段
- `to_dict()` 完整性（`cloud_file_size`/`needs_metadata`）

### Repositories 层 — 缺失的具体测试用例

**`repositories/track_repository.py`** — 覆盖率 ~33% (8/24 方法)

- `get_by_ids()` 批量查询
- `delete_batch()` 批量删除
- `get_albums()` / `get_album_tracks()` / `get_album_by_name()` 专辑相关
- `get_artists()` / `get_artist_tracks()` / `get_artist_albums()` / `get_artist_by_name()` 歌手相关
- `update_path()` / `update_cover_path()` / `update_fields()` 字段更新
- `get_playlist_tracks()` / `add_to_playlist()` 播放列表关联
- `sync_track_artists()` / `rebuild_track_artists()` / `update_artist_stats()` / `get_track_artist_names()` 多歌手关联表

**`repositories/cloud_repository.py`** — 覆盖率 ~59%

- `get_all_accounts(provider=)` provider 过滤
- `create_account()` / `update_account_token()` / `update_account_folder()` / `update_account_playing_state()` 账号操作
- `get_file_by_local_path()` / `get_files_by_parent()` / `get_all_downloaded()` / `cache_files()` 文件操作

**`repositories/base_repository.py`** — 覆盖率 0%

- `_get_connection()` 连接管理和线程安全
- `db_manager` vs `db_path` 两种初始化路径

**`repositories/queue_repository.py`** — 缺失边界测试

- `save()` 空队列 / 错误处理和回滚 / 混合来源
- `load()` 旧 schema 迁移 / 列检测

**`repositories/album_repository.py`** / **`artist_repository.py`** — 缺边界测试

- `refresh()` 空表 / 保留封面 / 多歌手分割
- `update_cover_path()` 不存在的记录

### Services 层 — 已有测试文件但覆盖不全

**`services/metadata/metadata_service.py`** — 覆盖率 ~60%

- `_save_mp3_metadata()` / `_save_flac_metadata()` / `_save_ogg_metadata()` / `_save_mp4_metadata()` / `_save_wav_metadata()` 各格式保存
- `_save_generic_metadata()` 通用保存

**`services/library/library_service.py`** — 覆盖率 ~60%

- `init_albums_artists()` / `refresh_albums_artists()` / `rebuild_albums_artists()` 专辑歌手初始化
- `get_tracks_by_ids()` 批量获取
- `get_artist_by_name()` / `get_artist_tracks()` / `get_artist_albums()` 歌手相关
- `get_album_by_name()` / `get_album_tracks()` 专辑相关

**`services/metadata/artist_parser.py`** — 覆盖率 ~60%

- `_try_split_by_known()` known artists 分割
- `split_artists_aware()` 空格分隔歌手名

**`services/playback/sleep_timer_service.py`** — 覆盖率 ~80%

- `_trigger_action()` 触发逻辑
- `_fade_step()` 淡出实现

### Infrastructure/System/Utils — 已有测试但覆盖不全

**`infrastructure/network/http_client.py`** — 缺少:

- `get_content()` 实际内容获取
- `download()` 带进度回调的下载 / 失败清理 / chunk size

**`system/theme.py`** — 缺少:

- `ThemeManager.register_widget()` 组件注册
- `_apply_and_broadcast()` 广播刷新
- `apply_global_stylesheet()` 全局样式表

**`system/event_bus.py`** — 缺少:

- `emit_playback_state()` 状态验证
- `emit_favorite_change()` 收藏变更
- `get_event_bus()` 便利函数
- `cache_cleanup_*` 信号

**`utils/lrc_parser.py`** — 缺少:

- `extract_qrc_xml()` QRC XML 提取
- `parse_char_word_lrc()` 字符级时间
- `fix_durations()` / `build_word_index()` / `find_current_word()` / `find_current_line()` / `ms_to_s()`

**`utils/match_scorer.py`** — 缺少:

- `_title_score` / `_artist_score` / `_album_score` 处理 dict/list 输入
- `SOURCE_PRIORITY` 平分时的优先级排序
- None/空字符串处理

**`utils/helpers.py`** — 缺少:

- `get_cache_dir()` 缓存目录解析（frozen/platformdirs/fallback）

---

## 三、按重要性排序的 Top 20 缺失测试

| 排名 | 模块 | 缺失内容 | 影响 |
|------|------|---------|------|
| 1 | `PlaybackService` | 整个播放流程（play/pause/next/prev/seek/volume） | 核心功能 |
| 2 | `PlayerEngine` (audio_engine) | 播放列表管理/播放控制/信号发射 | 核心功能 |
| 3 | `ConfigManager` | 60+ 配置项的 get/set | 全局配置 |
| 4 | `PlaybackHandlers` | Local/Cloud/Online 三种播放处理 | 核心功能 |
| 5 | `QueueService` | 队列持久化/恢复/播放模式 | 用户体验 |
| 6 | `TrackRepository` | 16个未测方法（专辑/歌手/批量操作） | 数据层 |
| 7 | `OnlineMusicService` | 搜索/排行榜/歌手详情/专辑详情 | 在线功能 |
| 8 | `LyricsService` | 歌词搜索/加载/保存 | 用户功能 |
| 9 | `CoverService` | 封面优先级/缓存/在线搜索 | 用户体验 |
| 10 | `OnlineMusicAdapter` | API 响应解析/标准化 | 数据解析 |
| 11 | `PlaylistService` | 播放列表 CRUD | 核心功能 |
| 12 | `FavoritesService` | 收藏 CRUD | 用户功能 |
| 13 | `DatabaseManager` | 建表/索引/FTS5 | 数据基础 |
| 14 | `DBWriteWorker` | 写入线程/队列/Future | 线程安全 |
| 15 | `CloudRepository` | 7个未测方法 | 云功能 |
| 16 | `SettingsRepository` | 全部5个方法未测 | 配置存储 |
| 17 | `Bootstrap` | 依赖注入/懒加载 | 架构 |
| 18 | `OnlineDownloadService` | 缓存/下载/质量回退 | 在线功能 |
| 19 | `MetadataService` (save) | 各格式元数据保存 | 数据写入 |
| 20 | `BaseRepository` | 连接管理/线程安全 | 数据基础 |

---

## 四、总结

- **完全无测试的文件**: 40个，主要集中在 Services 层（27个）和 Infrastructure 层（5个）
- **有测试但覆盖不足**: 约12个文件，尤其 `track_repository`（33%）、`cloud_repository`（59%）、`library_service`（60%）
- **预估总缺失测试用例**: 675+ 个
- **最关键缺口**: PlaybackService / PlayerEngine / ConfigManager — 这三个核心模块完全没有测试

建议按优先级（P0 > P1 > P2 > P3）顺序补充测试，优先确保播放核心链路和数据持久化层的测试覆盖。