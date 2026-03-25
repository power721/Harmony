# Harmony - 现代化音乐播放器

一款使用 Python 和 PySide6 构建的现代化桌面音乐播放器，采用清洁架构设计，支持本地音乐和云盘音乐的无缝播放。

## 功能特性

### 🎵 本地音乐播放
- **音乐库管理** - 扫描和管理本地音乐文件
- **智能元数据提取** - 自动提取音频文件标签信息（标题、艺术家、专辑等）
- **专辑封面显示** - 自动抓取和显示专辑封面
- **多种音频格式** - 支持 MP3、FLAC、OGG、M4A、WAV、WMA 等格式
- **全文搜索** - 基于 SQLite FTS5 的快速歌曲搜索，支持模糊匹配

### ☁️ 云盘音乐集成
- **夸克网盘支持** - 通过二维码登录夸克网盘
- **在线浏览** - 直接浏览网盘中的音乐文件
- **智能下载** - 自动下载云盘音乐到本地缓存
- **混合播放** - 本地音乐和云盘音乐无缝切换

### 🎧 QQ音乐集成
- **本地扫码登录** - 支持 QQ 和微信两种登录方式
- **二维码登录** - 自动生成二维码，手机扫码即可登录
- **凭证管理** - 自动保存登录凭证
- **多音质支持** - 支持多种音质（母带、全景声、无损、MP3）
- **歌词获取** - 支持翻译歌词和逐字歌词
- **封面获取** - 直接获取专辑封面和歌手图片 URL

### 📋 播放列表管理
- **自定义播放列表** - 创建和管理播放列表
- **播放队列** - 实时查看和管理当前播放队列
- **拖拽排序** - 拖拽调整播放队列中的歌曲顺序
- **队列持久化** - 应用重启后恢复播放队列

### ⏯️ 播放控制
- **完整播放控制** - 播放/暂停/上一曲/下一曲
- **多种播放模式** - 顺序播放、随机播放、列表循环、单曲循环
- **进度控制** - 精确的播放进度控制

### 🎤 歌词功能
- **自动下载歌词** - 自动从网络获取歌词
- **多源支持** - LRCLIB、网易云音乐、酷狗音乐、QQ音乐
- **智能匹配** - 基于标题、艺术家、专辑、时长的智能匹配算法
- **LRC 格式支持** - 支持 .lrc 歌词文件解析
- **同步显示** - 歌词与播放进度同步显示
- **高级歌词窗口** - 支持滚屏和高亮显示
- **繁简转换** - 自动将繁体中文歌词转换为简体中文

### 🖼️ 封面管理
- **自动封面获取** - 自动从网络获取专辑封面（网易云音乐、iTunes、MusicBrainz、Last.fm）
- **智能匹配** - 使用 MatchScorer 算法精确匹配封面
- **手动下载封面** - 支持手动选择和下载专辑封面（网易云音乐、QQ音乐、iTunes、Last.fm）
- **艺术家封面** - 搜索和下载艺术家封面（网易云音乐、QQ音乐、iTunes）
- **封面预览** - 下载前预览封面效果

### 🤖 AI 元数据增强
- **AI 标签识别** - 使用 AI 模型从文件名智能提取音乐元数据
- **自动补全** - 自动补全缺失的标题、艺术家、专辑信息
- **OpenAI 兼容** - 支持所有 OpenAI 兼容的 AI API
- **音频指纹识别** - 通过 AcoustID 识别未知音乐

### 🎨 现代化界面
- **Spotify 风格设计** - 简约现代的 UI 设计
- **迷你播放器** - 小巧的悬浮播放窗口，支持拖拽移动
- **系统托盘** - 最小化到系统托盘，后台播放
- **响应式布局** - 适配不同屏幕尺寸
- **专辑/艺术家视图** - 卡片式浏览专辑和艺术家

### ⌨️ 其他功能
- **全局快捷键** - 支持系统级媒体键控制
- **播放历史** - 自动记录播放历史
- **收藏功能** - 收藏喜爱的歌曲
- **多语言支持** - 中文/英文界面切换
- **状态恢复** - 重启后恢复播放状态

## 安装

### 环境要求

- Python 3.10 或更高版本
- 支持的操作系统：Windows、Linux、macOS

### 安装步骤

```bash
# 克隆仓库
git clone https://github.com/power721/music-player.git
cd music-player

# 安装依赖
uv sync

# 运行应用
uv run python main.py
```

### 依赖项

依赖项由 `pyproject.toml` 管理，使用 uv 安装：

| 依赖 | 用途 |
|------|------|
| PySide6 | Qt6 GUI 框架 |
| mutagen | 音频元数据提取 |
| requests | HTTP 请求 |
| beautifulsoup4 | 歌词爬取 |
| lxml | HTML 解析 |
| pymediainfo | 媒体信息提取 |
| qrcode | 二维码生成 |
| openai | AI 元数据增强 |
| opencc-python-reimplemented | 繁简转换 |
| pyacoustid | 音频指纹识别 |
| qqmusic-api-python | QQ音乐 API |
| pycryptodome | 加密解密（QQ音乐） |

## 使用说明

### 本地音乐

1. 点击左下角的"添加音乐"按钮
2. 选择包含音乐文件的文件夹
3. 音乐将被扫描并添加到音乐库
4. 点击歌曲即可播放

### 云盘音乐

1. 点击侧边栏的"云盘"选项卡
2. 点击"登录"按钮，显示二维码
3. 使用手机夸克网盘 APP 扫描二维码登录
4. 浏览云盘文件夹，点击音乐文件开始播放
5. 音乐将自动下载到本地缓存目录

### QQ音乐登录

1. 进入设置 -> QQ音乐配置
2. 点击"扫码登录"按钮
3. 选择登录方式：QQ 或微信
4. 使用手机 QQ 或微信扫描二维码
5. 在手机上确认登录
6. 登录成功后凭证会自动保存

### 播放控制

- **播放/暂停**：点击底部控制栏的播放按钮或按空格键
- **切歌**：使用上一曲/下一曲按钮
- **进度控制**：拖动进度条或点击进度条位置
- **音量控制**：拖动音量滑块
- **播放模式**：点击播放模式按钮切换

### 快捷键

**主窗口快捷键：**
- `Space` - 播放/暂停
- `Ctrl + →` - 下一曲
- `Ctrl + ←` - 上一曲
- `Ctrl + ↑` - 音量增加
- `Ctrl + ↓` - 音量减少
- `Ctrl + M` - 切换迷你模式

**迷你播放器快捷键：**
- `Space` - 播放/暂停
- `Ctrl + →` - 下一曲
- `Ctrl + ←` - 上一曲
- `Ctrl + ↑` - 音量增加
- `Ctrl + ↓` - 音量减少
- `Ctrl + M` - 关闭迷你播放器

## 架构说明

### 技术栈

- **GUI 框架**: PySide6 (Qt6)
- **音频引擎**: Qt Multimedia (QMediaPlayer)
- **数据库**: SQLite3 with FTS5
- **元数据提取**: mutagen, pymediainfo
- **网络请求**: requests
- **歌词解析**: BeautifulSoup4, lxml

### 核心架构（Harmony 3.0）

项目采用**清洁分层架构**，通过依赖反转实现松耦合：

```
app/           → 应用启动和依赖注入
domain/        → 纯领域模型（无外部依赖）
repositories/  → 数据访问抽象层
services/      → 业务逻辑层
infrastructure/→ 技术实现层
ui/            → PySide6 用户界面
system/        → 应用级组件
utils/         → 工具类
```

### 层依赖关系

```
UI → Services → Repositories → Infrastructure
              ↘ Domain ↗
```

- **UI** 仅依赖 **Services** 和 **Domain**
- **Services** 依赖 **Repositories** 和 **Domain**
- **Repositories** 依赖 **Infrastructure** 和 **Domain**
- **Domain** 无任何依赖（纯数据类）
- **Infrastructure** 实现技术细节

### 目录结构

```
Harmony/
├── app/                    # 应用启动和依赖注入
│   ├── application.py      # 应用单例
│   └── bootstrap.py        # 依赖注入容器
├── domain/                 # 领域模型（纯数据类）
│   ├── track.py           # 音乐轨道实体
│   ├── playlist.py        # 播放列表实体
│   ├── playlist_item.py   # 播放项抽象
│   ├── playback.py        # 播放状态枚举
│   ├── cloud.py           # 云盘实体
│   ├── album.py           # 专辑聚合实体
│   ├── artist.py          # 艺术家聚合实体
│   └── history.py         # 播放历史
├── repositories/           # 数据访问层
│   ├── track_repository.py
│   ├── playlist_repository.py
│   ├── cloud_repository.py
│   ├── queue_repository.py
│   └── interfaces.py       # 仓储接口
├── services/               # 业务逻辑层
│   ├── playback/          # 播放服务
│   │   ├── playback_service.py
│   │   └── queue_service.py
│   ├── library/           # 音乐库服务
│   │   └── library_service.py
│   ├── lyrics/            # 歌词服务
│   │   ├── lyrics_service.py
│   │   └── lyrics_loader.py
│   ├── metadata/          # 元数据服务
│   │   ├── metadata_service.py
│   │   └── cover_service.py
│   ├── cloud/             # 云盘服务
│   │   ├── quark_service.py
│   │   ├── download_service.py
│   │   └── qqmusic/       # QQ音乐服务
│   │       ├── qqmusic_service.py
│   │       ├── client.py
│   │       ├── crypto.py
│   │       └── common.py
│   └── ai/                # AI 服务
│       ├── ai_metadata_service.py
│       └── acoustid_service.py
├── infrastructure/         # 技术实现层
│   ├── audio/             # 音频引擎
│   │   └── audio_engine.py
│   ├── database/          # 数据库
│   │   └── sqlite_manager.py
│   ├── network/           # 网络客户端
│   │   └── http_client.py
│   └── cache/             # 文件缓存
│       └── file_cache.py
├── ui/                     # 用户界面
│   ├── windows/           # 窗口
│   │   ├── main_window.py
│   │   └── mini_player.py
│   ├── views/             # 视图
│   │   ├── library_view.py
│   │   ├── playlist_view.py
│   │   ├── queue_view.py
│   │   └── cloud_view.py
│   └── widgets/           # 控件
│       ├── player_controls.py
│       ├── lyrics_widget_pro.py
│       ├── cover_download_dialog.py
│       ├── album_cover_download_dialog.py
│       ├── artist_cover_download_dialog.py
│       ├── settings_dialog.py
│       ├── cloud_login_dialog.py
│       ├── qqmusic_qr_login_dialog.py
│       ├── equalizer_widget.py
│       ├── help_dialog.py
│       ├── album_card.py
│       └── artist_card.py
├── system/                 # 系统组件
│   ├── config.py          # 配置管理
│   ├── event_bus.py       # 事件总线
│   ├── i18n.py            # 国际化
│   └── hotkeys.py         # 全局快捷键
├── utils/                  # 工具类
│   ├── helpers.py         # 辅助函数
│   ├── lrc_parser.py      # LRC 解析器
│   └── match_scorer.py    # 智能匹配算法
├── tests/                  # 测试
│   ├── test_domain/       # 领域模型测试
│   ├── test_services/     # 服务层测试
│   ├── test_repositories/ # 数据访问层测试
│   ├── test_infrastructure/ # 基础设施测试
│   ├── test_ui/           # 用户界面测试
│   ├── test_utils/        # 工具类测试
│   └── test_system/       # 系统组件测试
├── translations/           # 翻译文件
│   ├── en.json
│   └── zh.json
└── main.py                 # 应用入口
```

### 关键设计模式

- **依赖注入**: 通过 Bootstrap 容器管理组件依赖
- **EventBus 模式**: 集中式事件总线，解耦组件通信
- **单例模式**: EventBus、Bootstrap、CloudDownloadService 使用单例
- **工厂模式**: PlaylistItem 使用工厂方法创建不同类型的播放项
- **线程本地存储**: DatabaseManager 使用 thread-local 确保线程安全
- **数据类模式**: 使用 `@dataclass` 定义领域模型

### 核心抽象

**PlaylistItem** - 统一的播放项抽象，支持本地和云盘文件：
- `is_local` / `is_cloud` - 判断来源类型
- `needs_download` - 云盘文件是否需要下载
- `from_track()` / `from_cloud_file()` - 工厂方法
- `to_play_queue_item()` - 转换为持久化模型

**MatchScorer** - 智能匹配算法：

双模式评分系统：
- **歌词模式**（标题优先）：标题 35%、艺术家 30%、专辑 15%、时长 20%
- **封面模式**（专辑优先）：标题 15%、艺术家 30%、专辑 35%、时长 20%

评分特性：
- 精确匹配：完全一致得 100 分
- 规范化匹配：忽略大小写、标点符号、空格
- 智能去噪：自动移除 "(Official)"、"[MV]"、"(Lyric Video)" 等常见后缀
- 多艺术家处理：支持 "feat."、"&"、"," 等分隔符，提取主要艺术家
- 时长容差：±30 秒内视为完全匹配，超出后按比例扣分
- 词语重叠：使用 Jaccard 相似度计算部分匹配
- QQ 音乐优先：相同分数时优先选择 QQ 音乐源

总分范围：0-100 分，越高表示匹配度越高

**EventBus** - 集中式事件信号：
- 播放事件：`track_changed`、`playback_state_changed`、`position_changed`
- 下载事件：`download_started`、`download_progress`、`download_completed`
- UI 事件：`lyrics_loaded`、`metadata_updated`、`cover_updated`
- 库事件：`tracks_added`、`playlist_created`、`favorite_changed`

## 数据存储

### 数据库（Harmony.db）

所有数据统一存储在 SQLite 数据库中。

- **位置**: `./Harmony.db`（项目根目录）

**表结构**:
- `tracks` - 本地音乐库
- `albums` - 专辑聚合
- `artists` - 艺术家聚合
- `playlists` / `playlist_items` - 播放列表
- `play_history` - 播放历史
- `favorites` - 收藏
- `cloud_accounts` - 云盘账号
- `cloud_files` - 云盘文件缓存
- `play_queue` - 持久化播放队列
- **`settings`** - 应用配置存储（统一配置管理）

### Settings 表

应用的配置（播放模式、音量、AI 设置等）存储在 `settings` 表中：

**存储内容**:
- 播放器设置：音量、播放模式、播放源
- 播放状态：当前曲目 ID、播放位置
- 云盘设置：账号 ID、下载目录
- UI 设置：语言、窗口几何、视图类型
- AI 设置：API 地址、密钥、模型
- AcoustID 设置：API 密钥

**表结构**:
```sql
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### 翻译文件

- **位置**: `translations/*.json`
- **支持语言**: 中文（zh）、英文（en）

## 开发

### 运行测试

```bash
# 运行所有测试
uv run pytest tests/

# 运行特定测试模块
uv run pytest tests/test_domain/
uv run pytest tests/test_repositories/

# 显示测试覆盖率
uv run pytest tests/ -v

# 手动测试
uv run python main.py
```

### 测试覆盖

项目包含 270+ 单元测试，覆盖：
- **领域模型**: Track, Playlist, PlaylistItem, Playback, Cloud, Album, Artist, History
- **数据访问层**: TrackRepository, PlaylistRepository, QueueRepository
- **服务层**: LibraryService, MetadataService
- **基础设施**: FileCache, HttpClient
- **工具类**: Helpers, LrcParser, MatchScorer
- **系统组件**: EventBus

### 代码风格

项目遵循以下代码风格：
- 使用 PEP 8 规范
- 类型注解使用 `typing` 模块
- 数据类使用 `@dataclass` 装饰器
- 日志使用 Python logging 模块
- 日志格式: `'[%(levelname)s] %(name)s - %(message)s'`

### 架构规则

AI 开发者应遵循以下规则：
1. 保持分层架构的清晰性
2. Domain 层不得导入其他模块
3. UI 只能依赖 Services 和 Domain
4. Services 应避免 UI 逻辑
5. 使用 EventBus 进行跨组件通信
6. 保持线程安全

## 打包发布

项目提供了跨平台打包脚本：

```bash
# Linux
./build_linux.sh

# macOS
./build_macos.sh

# Windows
build_windows.bat
```

详见 [BUILD.md](BUILD.md)。

## 常见问题

### Q: 为什么云盘音乐播放失败？
A: 请确保：
- 已成功登录夸克网盘账号
- 网络连接正常
- 云盘文件是支持的音频格式

### Q: QQ音乐登录失败？
A: 检查：
- 网络连接是否正常
- 是否安装了 `qqmusic-api-python` 依赖
- 二维码是否已过期（有效期约 2 分钟）

### Q: 歌词无法显示？
A: 检查：
- 网络连接是否正常
- 歌词文件是否与音频文件同名（.lrc 格式）
- 尝试手动下载歌词

### Q: 应用崩溃后如何恢复播放状态？
A: 应用会自动保存播放队列和状态，重新启动后会自动恢复（不会自动播放）。

### Q: 迷你播放器窗口标题显示什么？
A: 播放时显示 "歌曲名 - 艺术家"，暂停/停止时显示应用名称。

### Q: 如何使用 AI 元数据增强功能？
A: 在设置中配置 AI API（支持 OpenAI 兼容接口），然后在音乐库中选择歌曲进行元数据增强。

## 许可证

本项目采用 MIT 许可证 - 详见 LICENSE 文件

## 致谢

- Qt 社区提供的优秀框架
- mutagen 提供的音频元数据处理
- LRCLIB 提供的免费歌词 API
- 所有贡献者的支持

## 联系方式

- 项目主页: [GitHub Repository](https://github.com/power721/music-player)
- 问题反馈: [GitHub Issues](https://github.com/power721/music-player/issues)
