# Unified Cover Preview Design

## Goal

统一详情页封面预览的样式和交互，让本地与在线页面在点击封面后的体验保持一致：

- 无边框、无 title bar
- 支持拖动窗口
- 点击图片外任意位置关闭
- 按 `Esc` 关闭
- 本地图片和在线图片都使用同一套展示逻辑

## Scope

本次覆盖以下详情页的封面预览行为：

- `ui/views/album_view.py`
- `ui/views/artist_view.py`
- `ui/views/genre_view.py`
- `plugins/builtin/qqmusic/lib/online_detail_view.py`

本次会新增一个共享封面预览组件，并补对应 UI 测试。

本次不做：

- 修改列表悬浮封面预览逻辑
- 修改非详情页的图片放大行为
- 引入主窗口级全局 overlay 管理器
- 为封面预览增加缩放、旋转、保存图片等额外功能

## Current State

当前仓库内的详情页封面预览实现分裂：

- `AlbumView` 使用 `AlbumCoverDialog`
- `ArtistView` 使用 `ArtistCoverDialog`
- `OnlineDetailView` 使用单独的异步图片对话框逻辑
- `GenreView` 没有点击封面查看大图能力

这些实现存在几个问题：

- 样式不一致，有的有系统窗口边框，有的没有
- 关闭行为不一致，不能统一做到“点外部关闭”
- 逻辑重复，本地和在线图片加载代码散落在多个文件
- 后续再调样式或交互需要改多处代码

## Recommended Approach

采用“共享预览组件 + 各详情页接入”的方案。

原因：

- 可以一次统一四个页面的视觉和交互
- 能消除重复弹窗代码，降低维护成本
- 在线图片异步加载和线程清理可以集中处理
- 相比主窗口级 overlay，改动范围更可控，适合这次需求

不采用“每个页面分别修一遍”的方案，因为那会继续保留三套甚至四套实现，后续维护成本仍然偏高。

不采用“主窗口全局 overlay 管理器”的方案，因为这会引入更大范围的窗口层级和宿主集成改动，不适合当前需求规模。

## Design

### Shared Component

新增一个共享封面预览对话框组件，建议放在 `ui/dialogs/` 下，负责：

- 显示本地文件路径或在线 URL 对应的大图
- 使用统一的无边框窗口样式
- 在内容区外点击时关闭
- 支持按住内容区域拖动窗口
- 支持 `Esc` 关闭
- 按屏幕可用区域限制最大显示尺寸并保持等比缩放

组件对外只暴露简单调用接口，例如传入：

- 图片来源（本地路径或 URL）
- 标题文本
- 可选的高分辨率 URL

调用方不再自行创建专用对话框类。

### Visual and Interaction Model

统一后的预览层遵循以下规则：

- 窗口无边框、无系统 title bar
- 背景使用半透明遮罩，突出居中的图片内容
- 图片区域本身不显示额外边框装饰
- 点击图片区域外任意位置立即关闭
- 点击图片区域并拖动时移动整个窗口
- `Esc` 关闭窗口

这里的“点击外部关闭”定义为点击预览图片容器外的遮罩区域，不要求点击图片本体关闭，避免和拖动冲突。

### Loading Model

共享组件同时支持两种图片来源：

- 本地文件：直接读取并展示
- 在线 URL：先查缓存，未命中时异步下载，再展示

在线加载延续现有缓存策略，优先复用项目已有缓存/网络基础设施，避免在新组件中重新发明一套下载缓存机制。

加载中的展示规则：

- 初始显示统一的加载态
- 下载成功后替换为实际图片
- 下载失败时显示统一失败文案

### Detail View Integration

四个详情页统一接入共享组件：

- `AlbumView`
  - 删除 `AlbumCoverDialog`
  - `_on_cover_clicked()` 改为调用共享预览组件
- `ArtistView`
  - 删除 `ArtistCoverDialog`
  - `_on_cover_clicked()` 改为调用共享预览组件
- `GenreView`
  - 将封面改为可点击
  - 新增 `_on_cover_clicked()`，调用共享预览组件
- `OnlineDetailView`
  - 保留现有封面 URL 推导逻辑，继续在 QQ 封面地址可用时替换为更高分辨率版本
  - 删除现有 `_show_cover_dialog_async()` 内的专用弹窗实现
  - 改为调用共享预览组件

### Thread and Lifecycle Handling

在线图片预览的后台加载必须在窗口关闭时安全停止，避免遗留线程。

组件需要保证：

- 重复打开新预览前不会复用已经失效的加载对象
- 窗口关闭时停止仍在运行的异步加载
- 不依赖调用方自己管理预览加载线程

这样 `OnlineDetailView` 不再需要保留专用的大图线程管理逻辑，相关责任转移到共享组件内部。

### File Organization

建议的代码组织如下：

- 新增共享组件文件：
  - `ui/dialogs/cover_preview_dialog.py`
- 更新调用方：
  - `ui/views/album_view.py`
  - `ui/views/artist_view.py`
  - `ui/views/genre_view.py`
  - `plugins/builtin/qqmusic/lib/online_detail_view.py`
- 新增或更新测试：
  - `tests/test_ui/test_cover_preview_dialog.py`
  - `tests/test_ui/test_genre_view.py`
  - `tests/test_ui/test_online_detail_view_actions.py`
  - 如有必要补充 `AlbumView` / `ArtistView` 轻量接入测试

## Error Handling

需要覆盖以下失败路径：

- 本地文件路径不存在或图片无法读取
- 在线请求失败
- 下载成功但图片数据无法解码
- 对话框关闭时后台任务尚未完成

失败时组件应保持可关闭，不抛出未处理异常，不阻塞主线程。

## Testing Strategy

实现按 TDD 推进，至少覆盖：

- 共享预览组件点击遮罩关闭
- 共享预览组件 `Esc` 关闭
- 共享预览组件拖动时更新窗口位置的基础行为
- `GenreView` 封面点击能打开统一预览
- `OnlineDetailView` 点击封面走统一预览入口
- 在线预览关闭时后台加载能正确清理

测试优先验证行为，不绑定过细的内部实现细节，避免未来样式微调导致测试脆弱。

## Acceptance Criteria

满足以下条件即视为完成：

1. 四个详情页的封面点击后都打开同一种预览样式。
2. 预览窗口无边框、无 title bar。
3. 预览窗口支持拖动。
4. 点击图片外区域会关闭预览。
5. 按 `Esc` 会关闭预览。
6. `GenreView` 新增封面点击放大能力。
7. `OnlineDetailView` 仍能使用高分辨率封面 URL。
8. 不再保留 `AlbumCoverDialog`、`ArtistCoverDialog` 这类重复实现。
9. 相关测试覆盖新增统一行为。

## Risks and Mitigations

### Drag vs Close Conflict

风险：如果整个窗口都绑定点击关闭，拖动手势会和关闭手势冲突。

缓解：只在遮罩区域点击关闭，图片内容区域负责拖动，不把“点击任意位置关闭”实现成“所有区域都关闭”。

### Async Cleanup

风险：在线图片预览关闭时线程未退出，造成测试或退出流程告警。

缓解：将异步加载生命周期集中在共享组件内部，在关闭事件中统一停止并回收。

### Theme Consistency

风险：新组件和现有主题体系脱节，导致不同主题下视觉不协调。

缓解：背景、加载态、失败态都读取现有主题 token，而不是硬编码颜色。
