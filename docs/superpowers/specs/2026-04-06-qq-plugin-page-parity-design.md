# QQ Plugin Page Parity Design

## Goal

在 `feature/plugin-system` worktree 内，专项迁移旧 QQ 在线页的高价值页面功能，让插件页在交互路径、信息密度和关键动作上接近旧实现，同时保持插件边界，不把宿主专属耦合重新带回插件体系。

## Scope

本次只覆盖 QQ 音乐插件页相关的页面能力迁移，主要目标文件是：

- `plugins/builtin/qqmusic/lib/root_view.py`
- `plugins/builtin/qqmusic/lib/provider.py`
- `plugins/builtin/qqmusic/lib/client.py`
- `tests/test_plugins/test_qqmusic_plugin.py`

旧实现仅作为对照源：

- `ui/views/legacy_online_music_view.py`

本次不做：

- 恢复宿主 `OnlineMusicView` 为主入口
- 回退插件化架构
- 无关 QQ 页的全局重构
- 把旧页所有线程模型原样复制进插件页

## Current State

当前插件页已经具备最小可用能力：

- QQ 登录/退出
- 歌曲、歌手、专辑、歌单四类搜索
- 热搜、搜索历史、补全
- 榜单展示与榜单歌曲播放
- 推荐/收藏摘要入口
- 艺人、专辑、歌单详情
- 单曲播放、加入队列、下一首播放、下载

但和旧页相比，插件页仍明显偏“精简版”：

- 搜索结果仍是简化列表，缺少旧页的结果视图层次
- 详情页只有单曲列表和单曲动作，没有旧页的批量控制
- 推荐和收藏仍是摘要列表，不是旧页的卡片式入口
- 榜单缺少双视图、批量动作和更高密度交互
- 搜索体验没有旧页的弹层、导航恢复、请求协调能力

## Gap Inventory

### P0

#### 1. Search Results Structure

旧页搜索结果分为四类专用视图：

- 歌曲：表格、分页、双击播放、右键批量动作
- 歌手：`OnlineGridView` + load more
- 专辑：`OnlineGridView` + load more
- 歌单：`OnlineGridView` + load more

插件页当前四类结果都落在简单列表或简单表格，无法达到旧页交互密度。

#### 2. Detail Page Capability

旧页详情页依赖 `OnlineDetailView`，支持：

- `play all`
- `add all to queue`
- `insert all to queue`
- 从艺人详情跳专辑
- 与搜索/推荐/收藏页之间的回退恢复

插件页详情页当前仅支持单曲级操作，无法覆盖旧页主路径。

#### 3. Recommendation and Favorites Presentation

旧页将推荐和收藏展示为卡片区，并按数据类型分流：

- 推荐歌曲进入详情歌曲页
- 推荐歌单进入歌单列表或歌单详情
- 收藏歌曲进入歌曲详情
- 收藏歌单/专辑/歌手进入对应列表页

插件页当前只有摘要列表，虽然能打开部分内容，但表现和旧页差距大。

#### 4. Ranking Interaction

旧页榜单支持：

- 表格/列表双视图切换
- 激活播放
- 收藏切换
- 下载
- 批量队列动作

插件页当前只有基础榜单表格和双击播放。

### P1

#### 5. Search Experience

旧页的搜索体验包含：

- 热词弹层与历史联动
- 输入清空后的主界面恢复
- 补全防抖
- 过期请求忽略
- ESC 清理搜索相关浮层

插件页目前仅有静态热词列表、历史列表和同步补全。

#### 6. Navigation Recovery

旧页通过导航栈恢复来源页面，能在搜索结果、详情页、收藏列表之间往返。

插件页当前只有 `_detail_return_page`，复杂路径回退会丢上下文。

#### 7. Visual/Theming Fidelity

旧页大量使用 `ThemeManager` 与 `t()`；插件页仍有较多硬编码中文和基础控件样式。

### P2

#### 8. Deep Host Integrations

旧页有更深的宿主级能力：

- 下载进度和取消
- 缓存优先播放
- 批量下载线程管理
- 收藏同步到宿主库与歌单

插件页已经通过 `PluginMediaBridge` 拿到基础能力，但离旧页还有差距。

## Recommended Approach

采用“先补页面结构与交互骨架，再补 QQ 专项业务入口”的渐进迁移方案。

原因：

- 当前插件 API、provider、client 已足够支撑大部分页面复刻
- 直接整体搬运旧页会重新引入宿主耦合，破坏插件边界
- 先做结构对齐，可以尽快把插件页提升到接近旧页的可用层级

不采用“整体拷贝旧页”的方案，因为旧页依赖：

- `OnlineMusicService`
- `OnlineDownloadService`
- 宿主 `Bootstrap`
- 宿主事件与收藏/歌单集成

这些依赖在插件环境下只能部分复用，强搬会增加回归风险。

## Design

### Architecture

页面仍由 `QQMusicRootView` 作为插件入口，继续依赖：

- `QQMusicOnlineProvider` 作为页面提供方
- `QQMusicPluginClient` 作为数据聚合层
- `PluginMediaBridge` 作为播放/下载/入队桥接

迁移的重点不是复制宿主服务层，而是将旧页的高价值 UI 结构和操作流迁到插件页，并在需要时通过 provider/client 做数据适配。

### UI Composition

`QQMusicRootView` 将扩展为三个主区域：

- 首页：收藏卡片区、推荐卡片区、热搜/历史、榜单区
- 结果页：歌曲结果视图、歌手/专辑/歌单网格视图
- 详情页：批量动作栏 + 曲目列表 + 返回恢复

优先复用现有通用 UI 组件：

- `ui.widgets.recommend_card.RecommendSection`
- `ui.views.online_grid_view.OnlineGridView`
- `ui.views.online_detail_view.OnlineDetailView`
- `ui.views.online_tracks_list_view.OnlineTracksListView`

这样可以更接近旧页，也能减少插件页自己维护样式和交互状态的成本。

### Data Flow

`root_view` 不直接做复杂 QQ 结构解析，尽量将数据适配放在 `client.py`：

- `client.py` 负责将 QQ API/旧 QQ service 返回结构整理为插件页直接可消费的字典
- `provider.py` 继续暴露页面所需统一方法
- `root_view.py` 只负责视图状态、页面跳转和用户动作

对推荐/收藏，需要在 client 层补足：

- 推荐卡片元信息
- 收藏分组元信息
- 详情页或列表页所需的歌曲/歌单/专辑/歌手条目结构

### Navigation Model

插件页增加一个轻量导航栈，记录：

- 来源页面类型
- 当前结果页子视图
- 收藏/推荐来源的标题和原始数据
- 详情页来源

目标是复刻旧页“从哪里来就回哪里去”的主路径，不追求完全一致的内部状态模型。

### Search Model

搜索迁移分两层：

- 第一层：先补足歌曲表格、网格视图、分页、load more
- 第二层：再补热词弹层、防抖、过期请求忽略、ESC 行为

这样能先恢复主功能，再逐步逼近旧体验。

### Ranking Model

榜单区分两步演进：

- 先补列表视图和双视图切换
- 再补收藏/下载/批量动作

榜单和搜索歌曲结果应共享尽可能多的歌曲动作实现，避免维护两套不同逻辑。

### Media Actions

页面动作统一走 `context.services.media`：

- `play_online_track`
- `add_online_track_to_queue`
- `insert_online_track_to_queue`
- `cache_remote_track`

批量动作在插件页内做循环或组装，不新增宿主桥接接口，避免扩大插件 API 面。

“加入收藏”“加入歌单”这类深宿主动作不作为首批阻塞项；若后续补，需要先确认当前插件上下文是否已有稳定桥接。

## Migration Batches

### Batch A

目标：先补齐最核心的搜索和详情结构。

内容：

- 结果页升级为歌曲表格 + 歌手/专辑/歌单网格
- 增加歌曲分页
- 增加非歌曲 `load more`
- 详情页切换到可批量操作的通用详情视图
- 引入导航栈恢复主路径

### Batch B

目标：恢复首页“像旧页”的第一观感和常用入口。

内容：

- 收藏区改成卡片化
- 推荐区改成卡片化
- 按旧页逻辑区分歌曲型与歌单型入口
- 收藏/推荐点击后进入对应列表页或详情页

### Batch C

目标：补齐榜单交互。

内容：

- 榜单双视图切换
- 榜单列表视图
- 榜单批量播放/入队/下载
- 右键菜单

### Batch D

目标：收尾搜索体验和视觉一致性。

内容：

- 热词弹层与历史联动
- 补全防抖与过期请求保护
- ESC 行为
- 文案和主题对齐

## Testing Strategy

测试集中在：

- `tests/test_plugins/test_qqmusic_plugin.py`

按批次补测试，不一次性重写整套插件测试：

- Batch A 测试结果页类型切换、分页、详情批量动作、导航返回
- Batch B 测试推荐/收藏卡片点击后的路由
- Batch C 测试榜单双视图和批量动作
- Batch D 测试热词/补全/历史状态恢复

保持 focused pytest 验证，不依赖当前不稳定的全量测试基线。

## Risks and Mitigations

### Risk 1: `root_view.py` 继续膨胀

缓解：

- 优先复用通用组件
- 将数据整理逻辑留在 `client.py`
- 当某一块达到可独立维护规模时，再拆成局部 helper

### Risk 2: 插件页重新引入宿主耦合

缓解：

- 只通过 `context.settings`、`context.services.media`、provider/client 访问宿主
- 不直接依赖宿主 `Bootstrap`
- 不重新启用旧宿主 `OnlineMusicView`

### Risk 3: API 返回结构不稳定

缓解：

- 尽量在 `client.py` 做字段归一化
- 测试中覆盖 QQ 结构适配的关键分支

### Risk 4: 首页与详情跳转状态错乱

缓解：

- 使用轻量导航栈而不是单个返回页指针
- 每个入口都明确记录来源状态

## Success Criteria

满足以下条件即可认为“插件页接近旧 QQ 页面功能”：

- 搜索四类结果具备旧页同等级的主要视图结构
- 详情页支持批量播放/入队主路径
- 首页收藏/推荐入口恢复为卡片化且可正确分流
- 榜单支持双视图和主要批量动作
- 搜索体验至少具备热词/历史/补全的旧页主路径
- 整体实现保持插件边界，不回退插件系统设计
