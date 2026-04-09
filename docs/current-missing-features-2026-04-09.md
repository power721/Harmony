# Harmony 当前缺失功能报告

> 生成日期: 2026-04-09
> 范围: 基于当前代码库状态的重新审计
> 说明: 本报告用于替代部分已过时的 `docs/missing-features.md` 结论

---

## 总结

当前代码库里，旧报告中的一部分缺失项已经补齐，但仍有几类功能缺口没有完成，主要集中在：

- README 仍宣称支持、但实现实际上只是占位或简化版的功能
- 数据层已有基础结构、但用户不可见或统计逻辑不完整的功能
- 高级播放能力和可视化能力
- 播放列表增强能力

从用户影响看，当前最值得优先补齐的是：

1. 删除/移动文件后的曲库清理
2. 播放历史计数与“最多播放/最近添加”入口
3. 真正的全局快捷键与系统媒体键支持

---

## 一、当前仍缺失或未完成的功能

### HIGH-01: 真正的全局快捷键 / 系统媒体键

- 严重度: 高
- 现状:
  - 当前实现基于 Qt `QShortcut`
  - 仅在应用窗口有焦点时生效
  - Linux 和 macOS 的系统级媒体键实现仍为空
- 影响:
  - 用户切换到其他应用后，媒体键控制不可靠或完全不可用
  - README 中“全局快捷键”表述与实际实现不完全一致
- 证据:
  - [`system/hotkeys.py`](/home/harold/workspace/music-player/system/hotkeys.py#L1)
  - [`system/hotkeys.py`](/home/harold/workspace/music-player/system/hotkeys.py#L34)
  - [`system/hotkeys.py`](/home/harold/workspace/music-player/system/hotkeys.py#L181)

### HIGH-02: 曲库缺少删除/移动文件检测

- 严重度: 高
- 现状:
  - 重新扫描目录时，只会扫描文件、提取元数据并执行 `batch_add`
  - 没有对磁盘上已不存在文件进行清理
  - 没有“移动文件后修复路径”的同步逻辑
- 影响:
  - 曲库中会残留无法播放的幽灵曲目
  - 用户整理本地音乐文件后，数据库状态与真实文件系统脱节
- 证据:
  - [`services/library/library_service.py`](/home/harold/workspace/music-player/services/library/library_service.py#L485)

### HIGH-03: “最多播放”统计不可靠，且无入口

- 严重度: 高
- 现状:
  - 历史仓储层已经实现 `get_most_played()`
  - `play_history` 表也有 `play_count` 字段
  - 但历史写入逻辑在冲突时只更新时间，不增加 `play_count`
  - 没有发现对应的 UI 页面或主入口
- 影响:
  - 即使后续接出 UI，当前统计结果也不可信
  - 现有数据结构价值未被真正利用
- 证据:
  - [`repositories/history_repository.py`](/home/harold/workspace/music-player/repositories/history_repository.py#L25)
  - [`repositories/history_repository.py`](/home/harold/workspace/music-player/repositories/history_repository.py#L99)
  - [`infrastructure/database/sqlite_manager.py`](/home/harold/workspace/music-player/infrastructure/database/sqlite_manager.py#L213)

### MID-01: 实时音频可视化

- 严重度: 中
- 现状:
  - 仓库内存在设计文档
  - 没有找到 `audio_visualizer_widget.py`
  - 没有找到 `supports_visualizer()`、`visualizer_frame` 的实际实现
- 影响:
  - 当前播放页缺少波形/频谱等动态反馈
  - 这项能力仍停留在设计层
- 证据:
  - [`docs/superpowers/specs/2026-04-03-realtime-visualizer-design.md`](/home/harold/workspace/music-player/docs/superpowers/specs/2026-04-03-realtime-visualizer-design.md#L47)

### MID-02: 智能播放列表

- 严重度: 中
- 现状:
  - 当前播放列表模型仅包含 `id`、`name`、`created_at`
  - 没有规则、筛选条件、自动更新逻辑
- 影响:
  - 无法创建“最近添加”“最多播放”“最近播放”“高评分”等自动列表
- 证据:
  - [`domain/playlist.py`](/home/harold/workspace/music-player/domain/playlist.py#L10)

### MID-03: 播放列表文件夹 / 分类

- 严重度: 中
- 现状:
  - 播放列表数据模型没有层级字段
  - 没有找到分类、树结构或文件夹式组织能力
- 影响:
  - 播放列表数量增长后，管理体验会迅速下降
- 证据:
  - [`domain/playlist.py`](/home/harold/workspace/music-player/domain/playlist.py#L10)

### MID-04: 最近添加视图

- 严重度: 中
- 现状:
  - `tracks.created_at` 已存在
  - 也建了 `created_at` 索引
  - 但没找到“最近添加”服务入口或 UI 入口
- 影响:
  - 用户无法快速查看最近导入的曲目
- 证据:
  - [`infrastructure/database/sqlite_manager.py`](/home/harold/workspace/music-player/infrastructure/database/sqlite_manager.py#L321)

### MID-05: 星级评分系统

- 严重度: 中
- 现状:
  - 当前只有收藏二值状态
  - 没找到评分字段、评分仓储、评分 UI
- 影响:
  - 无法做更细粒度的喜好表达
  - 也限制了智能播放列表的后续扩展

### MID-06: PLS 导入导出

- 严重度: 中
- 现状:
  - 当前只实现了 M3U 导入导出
  - 没有 PLS 支持
- 影响:
  - 与其他播放器的兼容性仍有限
- 证据:
  - [`services/library/playlist_service.py`](/home/harold/workspace/music-player/services/library/playlist_service.py#L152)

### MID-07: 设置备份 / 恢复

- 严重度: 中
- 现状:
  - 没有发现设置导出、导入、备份恢复入口
- 影响:
  - 迁移设备、重装系统、重置配置时成本高

### LOW-01: Gapless Playback

- 严重度: 低
- 现状:
  - 没有找到明确实现

### LOW-02: Crossfade

- 严重度: 低
- 现状:
  - 没有找到明确实现

### LOW-03: 播放速度调节

- 严重度: 低
- 现状:
  - 没有找到明确实现

### LOW-04: A-B 区间循环

- 严重度: 低
- 现状:
  - 没有找到明确实现

### LOW-05: ReplayGain / 音量标准化

- 严重度: 低
- 现状:
  - 没有找到明确实现

---

## 二、旧报告中已修复或已过时的项目

以下项目在旧报告里曾被列为缺失，但按当前代码状态看，已经不应再归类为缺失功能。

### FIXED-01: Genre 支持

- 当前状态:
  - `Track` 已包含 `genre`
  - 存在 `Genre` 领域模型
  - 存在 `genre_repository`
  - 主窗口已有 `GenresView` 和 `GenreView`
- 证据:
  - [`domain/track.py`](/home/harold/workspace/music-player/domain/track.py#L33)
  - [`domain/genre.py`](/home/harold/workspace/music-player/domain/genre.py)
  - [`repositories/genre_repository.py`](/home/harold/workspace/music-player/repositories/genre_repository.py)
  - [`ui/windows/main_window.py`](/home/harold/workspace/music-player/ui/windows/main_window.py#L403)

### FIXED-02: OPUS 支持

- 当前状态:
  - `SUPPORTED_FORMATS` 已包含 `.opus`
- 证据:
  - [`services/metadata/metadata_service.py`](/home/harold/workspace/music-player/services/metadata/metadata_service.py#L25)

### FIXED-03: QQ 在线详情页双击播放

- 当前状态:
  - 双击歌曲已调用 `_play_track`
- 证据:
  - [`plugins/builtin/qqmusic/lib/online_detail_view.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/online_detail_view.py#L2000)

### FIXED-04: QQ 在线下载取消

- 当前状态:
  - `_cancel_download()` 已实现
  - 下载进度对话框已连接取消逻辑
- 证据:
  - [`plugins/builtin/qqmusic/lib/online_music_view.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/online_music_view.py#L3043)
  - [`plugins/builtin/qqmusic/lib/online_music_view.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/online_music_view.py#L3103)

### FIXED-05: 云盘批量下载 / 下载取消

- 当前状态:
  - 云盘视图已有下载队列
  - 支持并发批量下载
  - 支持取消全部待下载任务
- 证据:
  - [`ui/views/cloud/cloud_drive_view.py`](/home/harold/workspace/music-player/ui/views/cloud/cloud_drive_view.py#L1848)
  - [`ui/views/cloud/cloud_drive_view.py`](/home/harold/workspace/music-player/ui/views/cloud/cloud_drive_view.py#L1979)

### FIXED-06: 播放队列拖拽重排

- 当前状态:
  - `queue_view` 已在 `_on_rows_moved()` 中同步引擎队列
- 证据:
  - [`ui/views/queue_view.py`](/home/harold/workspace/music-player/ui/views/queue_view.py#L1338)

### FIXED-07: 清除播放历史 / Service 接线

- 当前状态:
  - `PlayHistoryService.clear_history()` 已接入 repository
  - `get_most_played()` 也已从 service 接到 repository
  - 但“统计是否可信”和“是否有 UI 入口”仍是另外的问题
- 证据:
  - [`services/library/play_history_service.py`](/home/harold/workspace/music-player/services/library/play_history_service.py#L64)

### FIXED-08: M3U 导入导出

- 当前状态:
  - 播放列表已经支持 M3U 导入和导出
- 证据:
  - [`services/library/playlist_service.py`](/home/harold/workspace/music-player/services/library/playlist_service.py#L152)
  - [`ui/views/playlist_view.py`](/home/harold/workspace/music-player/ui/views/playlist_view.py#L636)

---

## 三、建议的优先级排序

### 第一阶段：先修“数据正确性”

- 删除/移动文件检测
- 播放历史 `play_count` 累加逻辑
- 最近添加 / 最多播放页面接入

### 第二阶段：修“README 承诺与实际不一致”的功能

- 真正的全局快捷键
- Linux / macOS 媒体键支持

### 第三阶段：增强用户组织能力

- 智能播放列表
- 播放列表分组 / 文件夹
- 星级评分
- 设置备份 / 恢复

### 第四阶段：高级体验增强

- 实时音频可视化
- Gapless
- Crossfade
- 播放速度
- A-B 循环
- ReplayGain

---

## 四、结论

当前仓库并不是“功能大量缺失”，而是处于一种更具体的状态：

- 基础播放器能力已经比较完整
- 旧报告中的若干缺项已经完成
- 仍然缺少的是高级能力、组织能力，以及少量会直接影响数据一致性的关键功能

如果只选最值得立刻做的三项，建议是：

1. 修复扫描后的失效文件清理
2. 修复播放历史计数并补出“最多播放/最近添加”
3. 落实真正的全局媒体键支持
