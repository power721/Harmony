# Playlist Folders Design

## Goal

为现有播放列表功能增加一级文件夹组织能力，让用户可以把播放列表归类到文件夹中，并通过拖拽在顶层与文件夹之间整理顺序。

首版范围明确如下：

- 只支持一级文件夹，不支持文件夹嵌套
- 未分组播放列表保留在顶层显示
- 文件夹节点只负责展开/折叠，不承载右侧内容页
- 首版支持拖拽移动与重排
- 删除文件夹时，文件夹内播放列表移动回顶层，不删除播放列表

## Scope

本次会覆盖：

- 数据库结构扩展与迁移
- 播放列表仓储与服务层能力扩展
- 播放列表左侧导航从平面列表升级为树形列表
- 文件夹 CRUD
- 拖拽移动与重排
- 对应 repository / service / UI 测试

本次不会做：

- 多级文件夹
- 文件夹详情页
- 文件夹汇总播放
- 智能播放列表
- 文件夹图标自定义
- 跨设备同步

## Current State

当前播放列表体系是纯平面结构：

- [`domain/playlist.py`](/home/harold/workspace/music-player/domain/playlist.py) 只有 `id`、`name`、`created_at`
- [`repositories/playlist_repository.py`](/home/harold/workspace/music-player/repositories/playlist_repository.py) 只支持平面播放列表 CRUD 和曲目增删
- [`ui/views/playlist_view.py`](/home/harold/workspace/music-player/ui/views/playlist_view.py) 左侧使用 `QListWidget` 渲染播放列表，没有分组层级
- 数据库中的 `playlists` 表也没有文件夹和显示顺序字段

这导致当播放列表数量增长后，左侧列表会迅速失去可管理性。

## Approaches Considered

### Approach A: 在 `playlists` 表上直接加 `folder_name`

优点：

- 改动最小
- 数据迁移简单

缺点：

- 文件夹不是正式实体，无法可靠表达文件夹顺序和重命名语义
- 首版要求支持拖拽排序、删除文件夹后回顶层，这些能力会变得别扭
- 后续如果要扩展文件夹行为，技术债会很快暴露

### Approach B: 新增 `playlist_folders` 表，并让 `playlists.folder_id` 指向它

优点：

- 文件夹语义清晰，是一级正式对象
- 更适合表达文件夹重命名、删除、排序、拖拽目标、名称唯一性
- 可以在不推翻结构的前提下继续扩展

缺点：

- 数据库、仓储、服务、UI 都要同步改造

### Approach C: 只在 UI 层做“分组显示”

优点：

- 实现快

缺点：

- 数据和 UI 分离
- 拖拽、事件同步、导入导出都容易出现状态不一致
- 不符合当前仓库分层设计

## Recommended Approach

采用 Approach B：新增独立 `playlist_folders` 表，并在 `playlists` 上增加 `folder_id` 与 `position`。

原因：

- 这最符合当前需求中“文件夹是正式对象”的语义
- 能自然支持拖拽、重排、删除文件夹回顶层
- 比“用字符串冒充文件夹”更稳，也更符合当前仓库的 repository / service 分层风格

## Data Model

### PlaylistFolder

新增一级文件夹实体，建议增加新领域模型 `PlaylistFolder`，字段如下：

- `id`
- `name`
- `position`
- `created_at`

说明：

- `name` 在文件夹维度内必须唯一，按大小写不敏感比较
- `position` 用于控制文件夹在顶层树中的显示顺序

### Playlist

扩展现有 `Playlist` 模型，新增：

- `folder_id: Optional[int]`
- `position: int`

语义：

- `folder_id = None` 表示顶层未分组播放列表
- `position` 表示同一容器内的顺序
  - 顶层播放列表：同一 `folder_id = NULL` 容器内排序
  - 文件夹内播放列表：同一 `folder_id = X` 容器内排序

## Database Design

### New Table

新增表：

```sql
CREATE TABLE IF NOT EXISTS playlist_folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    position INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

新增唯一索引：

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_playlist_folders_name_nocase
    ON playlist_folders(name COLLATE NOCASE)
```

### Playlist Table Migration

为 `playlists` 增加字段：

- `folder_id INTEGER NULL`
- `position INTEGER NOT NULL DEFAULT 0`

并增加索引：

- `(folder_id, position)`

### Migration Rules

迁移时执行以下规则：

1. 如果 `playlist_folders` 表不存在，则创建。
2. 如果 `playlists.folder_id` 不存在，则新增，默认 `NULL`。
3. 如果 `playlists.position` 不存在，则新增，默认 `0`。
4. 用当前 `playlists` 现有顺序初始化顶层 `position`，保证升级后左侧播放列表顺序不突然跳变。
5. 不迁移任何历史数据到文件夹，因为旧版本没有该概念，所有既有播放列表都保留在顶层。

## Repository Design

在 [`repositories/playlist_repository.py`](/home/harold/workspace/music-player/repositories/playlist_repository.py) 中新增文件夹相关能力。

### Read APIs

- `get_all_folders() -> list[PlaylistFolder]`
- `get_all_playlists() -> list[Playlist]`
- `get_playlist_tree() -> PlaylistTree`

其中 `get_playlist_tree()` 返回一个已经按顺序组装好的树形结构：

- 顶层文件夹列表
- 顶层未分组播放列表列表
- 每个文件夹下的播放列表列表

Repository 层负责从数据库读取并保持顺序正确，不把排序和归组责任留给 UI。

### Folder CRUD APIs

- `create_folder(name: str) -> int`
- `rename_folder(folder_id: int, name: str) -> bool`
- `delete_folder(folder_id: int) -> bool`

删除文件夹时必须在单个事务内完成：

1. 读取文件夹内播放列表
2. 将这些播放列表的 `folder_id` 置空
3. 重新分配这些播放列表的顶层 `position`
4. 删除文件夹行

### Move / Reorder APIs

- `move_playlist_to_folder(playlist_id: int, folder_id: int) -> bool`
- `move_playlist_to_root(playlist_id: int) -> bool`
- `move_playlist_between_folders(playlist_id: int, target_folder_id: int) -> bool`
- `reorder_root_playlists(playlist_ids: list[int]) -> bool`
- `reorder_folder_playlists(folder_id: int, playlist_ids: list[int]) -> bool`
- `reorder_folders(folder_ids: list[int]) -> bool`

这些接口都必须是事务性的。任一步失败时整次移动或重排回滚，不能留下半更新顺序。

## Service Design

在 [`services/library/playlist_service.py`](/home/harold/workspace/music-player/services/library/playlist_service.py) 中新增更高层的文件夹能力。

### Public Service API

- `get_playlist_tree()`
- `create_folder(name: str) -> int`
- `rename_folder(folder_id: int, name: str) -> bool`
- `delete_folder(folder_id: int) -> bool`
- `move_playlist_to_folder(playlist_id: int, folder_id: int) -> bool`
- `move_playlist_to_root(playlist_id: int) -> bool`
- `reorder_root_playlists(playlist_ids: list[int]) -> bool`
- `reorder_folder_playlists(folder_id: int, playlist_ids: list[int]) -> bool`
- `reorder_folders(folder_ids: list[int]) -> bool`

### Validation Rules

Service 层负责：

- 拒绝空文件夹名
- 拒绝全空白文件夹名
- 拒绝与现有文件夹名大小写不敏感冲突的名称
- 拒绝把播放列表移动到不存在的文件夹

播放列表重名仍然允许，保持当前行为不变。

## Event Design

当前 [`system/event_bus.py`](/home/harold/workspace/music-player/system/event_bus.py) 中已有：

- `playlist_created`
- `playlist_modified`
- `playlist_deleted`

本次新增：

- `playlist_structure_changed = Signal()`

用途：

- 文件夹创建
- 文件夹重命名
- 文件夹删除
- 播放列表移动到文件夹
- 播放列表移回顶层
- 文件夹重排
- 播放列表顺序重排

保留现有 `playlist_created` / `playlist_modified` 信号，避免影响右侧曲目区和其他既有调用方。

## UI Design

### Navigation Structure

[`ui/views/playlist_view.py`](/home/harold/workspace/music-player/ui/views/playlist_view.py) 左侧从 `QListWidget` 升级为树形控件。

顶层同时显示：

- 文件夹节点
- 顶层未分组播放列表节点

文件夹节点下面显示该文件夹内的播放列表节点。

### Node Behavior

- 点击文件夹：只展开/折叠，不切换右侧内容
- 双击文件夹：不触发播放，也不加载右侧
- 点击播放列表：正常加载右侧曲目区
- 双击播放列表：保留当前行为，加载并开始播放

### Actions

新增 UI 动作：

- “新建文件夹”按钮
- 文件夹右键菜单：
  - 重命名文件夹
  - 删除文件夹
- 播放列表右键菜单：
  - 移动到文件夹
  - 移出文件夹

M3U 导入后的新播放列表默认进入顶层，不强制用户立即放进文件夹。

### Drag and Drop Behavior

首版支持以下拖拽操作：

- 顶层播放列表之间重排
- 文件夹之间重排
- 文件夹内播放列表重排
- 顶层播放列表拖进文件夹
- 文件夹内播放列表拖回顶层
- 一个文件夹内播放列表拖到另一个文件夹

明确不支持：

- 把文件夹拖进文件夹
- 把播放列表拖到播放列表上形成嵌套

### Selection Persistence

如果当前选中的播放列表被移动到别处：

- 右侧内容保持当前播放列表
- 左侧树刷新后重新定位并选中该播放列表节点

如果当前选中的文件夹被删除：

- 因为文件夹本身不承载右侧内容，所以无需清空右侧

## Error Handling

需要覆盖以下失败路径：

- 创建文件夹时名称冲突
- 重命名文件夹时名称冲突
- 拖拽目标非法
- 删除文件夹时数据库事务失败
- 重排时传入的 ID 列表和实际容器内容不一致

处理规则：

- 非法操作直接拒绝，不更新 UI 到伪成功状态
- 仓储失败时回滚数据库事务
- Service 层返回失败并由 UI 弹出错误提示
- 拖拽失败后树视图刷新为数据库中的真实状态

## Testing Strategy

按 TDD 推进，至少覆盖以下测试面。

### Repository Tests

- 创建文件夹
- 文件夹名称唯一性
- 重命名文件夹
- 删除文件夹后播放列表移到顶层
- 顶层播放列表重排
- 文件夹重排
- 文件夹内播放列表重排
- 播放列表跨容器移动

### Service Tests

- 空文件夹名校验
- 文件夹名称冲突校验
- 不存在文件夹的移动校验
- `get_playlist_tree()` 的树形组装正确性

### UI Tests

- 左侧树正确渲染顶层文件夹和顶层播放列表
- 点击文件夹只展开/折叠，不切右侧内容
- 点击播放列表正常加载右侧曲目
- 拖拽播放列表进文件夹
- 拖拽播放列表回顶层
- 文件夹内播放列表重排
- 删除文件夹后树刷新且播放列表回顶层
- 当前选中播放列表在移动后仍保持选中与右侧内容一致

## Acceptance Criteria

满足以下条件即视为完成：

1. 用户可以创建、重命名、删除一级播放列表文件夹。
2. 旧播放列表升级后全部保留在顶层。
3. 顶层未分组播放列表与文件夹可以同时显示。
4. 文件夹点击只展开/折叠，不切换右侧内容。
5. 播放列表仍可正常点击、双击、播放、导入、导出。
6. 用户可以通过拖拽在顶层和文件夹之间移动播放列表。
7. 用户可以分别重排文件夹、顶层播放列表、文件夹内播放列表。
8. 删除文件夹时，文件夹内播放列表不会丢失，而是回到顶层。
9. 相关 repository、service、UI 测试覆盖新增行为。

## Risks and Mitigations

### Tree Refresh vs Selection Drift

风险：树结构刷新后，当前选中节点丢失，右侧内容与左侧高亮不同步。

缓解：以选中的播放列表 ID 为主键恢复节点选中状态，而不是依赖旧的 widget 引用。

### Drag-and-Drop Complexity

风险：拖拽目标组合较多，容易出现“UI 看起来成功但数据库没同步”的状态漂移。

缓解：拖拽落点只映射到少数明确仓储操作；操作完成后统一从数据库重载树，而不是在内存里手动拼接状态。

### Migration Order Stability

风险：已有用户升级后，顶层播放列表顺序发生变化。

缓解：迁移时按现有展示顺序补全 `position`，不使用不稳定的默认值覆盖旧顺序。
