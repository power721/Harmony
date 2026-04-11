# Harmony

[English](README.md)

Harmony 是一个使用 Python 和 PySide6 构建的桌面音乐播放器，结合了本地音乐库、云盘播放、插件化在线音乐能力，以及便于持续维护的分层架构。

## 主要特性

- 本地音乐库管理：支持目录扫描、元数据提取、内嵌封面读取、SQLite FTS5 搜索，以及专辑 / 艺术家 / 流派聚合
- 完整播放体验：播放队列持久化、多种播放模式、迷你播放器、当前播放窗口、睡眠定时器、均衡器界面、收藏、历史、最近添加、最多播放等视图
- 云盘播放：支持夸克和百度网盘，包含扫码登录、远程目录浏览、下载 / 缓存处理，以及分享链接搜索
- 插件系统：在线音乐源、歌词源、封面源、侧边栏入口、设置页都可以通过插件扩展
- 内置歌词 / 封面插件，以及内置 QQ 音乐插件，支持在线浏览、搜索、登录、队列操作、歌词和封面数据
- 可选 AI 元数据补全，兼容 OpenAI 风格接口；可选 AcoustID 音频指纹识别
- 支持中英文界面、主题系统、内置字体，以及在运行环境允许时的系统媒体键集成

## 内置插件

内置插件位于 [`plugins/builtin`](plugins/builtin)。外部插件可以通过 `设置 -> 插件` 从 zip 文件或 URL 安装。

| 插件 | 能力 |
| --- | --- |
| `qqmusic` | 在线音乐源、侧边栏入口、设置页、歌词源、封面源 |
| `lrclib` | 歌词源 |
| `netease_lyrics` | 歌词源 |
| `kuogo_lyrics` | 歌词源 |
| `netease_cover` | 封面源 |
| `itunes_cover` | 封面源 |
| `last_fm_cover` | 封面源 |

## 环境要求

- Python 3.11+
- `uv`
- Windows、Linux 或 macOS
- 如果要使用 `mpv` 后端，需要系统提供 `libmpv` 运行时

`mpv` 运行时说明：

- Linux（Debian/Ubuntu）：`sudo apt-get install libmpv-dev`
- macOS（Homebrew）：`brew install mpv`
- Windows：安装 `mpv`，或确保 `mpv-2.dll` 已在 `PATH` 中

## 快速开始

```bash
git clone https://github.com/power721/Harmony.git
cd Harmony

# 运行时依赖
uv sync

# 可选：开发工具，例如 pytest、pytest-qt、ruff、pyright
uv sync --extra dev --group dev

# 可选：开发环境下载内置字体
./download_fonts.sh

# 启动应用
uv run python main.py
```

字体相关说明见 [`docs/font-bundling.md`](docs/font-bundling.md)。

## 日常使用

- 点击 `Add Music` 扫描本地目录并建立音乐库
- 打开 `Cloud Drive` 登录夸克或百度网盘并浏览远程文件
- 打开 `设置 -> 插件` 启用、禁用或安装插件
- 打开 `设置 -> 播放` 在 `mpv` 与 `Qt Multimedia` 之间切换
- 打开 `设置 -> AI` 或 `设置 -> AcoustID` 配置可选的元数据服务

## 开发

常用命令：

```bash
# 运行应用
uv run python main.py

# 运行完整测试
uv run pytest tests/

# 较快的 UI 测试
uv run pytest tests/test_ui/ -m "not slow"

# Lint
uv run ruff check .

# 按当前平台打包
./build.sh

# 显式指定平台打包
uv run python build.py linux
uv run python build.py macos
uv run python build.py windows

# Linux 发布 / AppImage 流程
./release.sh
```

[`pytest.ini`](pytest.ini) 中定义了这些标记：

- `unit`
- `integration`
- `slow`

## 架构

Harmony 采用分层架构：

```text
UI -> Services -> Repositories -> Infrastructure
      \-------> Domain <-------/
```

顶层目录说明：

```text
app/            应用启动与依赖装配
domain/         纯领域模型
repositories/   基于 SQLite 的持久化适配层
services/       音乐库、播放、云盘、下载、歌词、元数据、AI 等服务
infrastructure/ 音频后端、数据库、缓存、网络、字体、安全等技术实现
system/         配置、事件总线、主题、国际化、快捷键、插件宿主
ui/             窗口、对话框、控件、视图、控制器、工作线程
plugins/        内置插件实现
packages/       本地插件 SDK 包（`harmony-plugin-api`）
tests/          按层拆分的 pytest 测试
docs/           设计文档、问题分析、实现记录
data/           开发模式下的可写应用数据
```

## 运行时说明

- 开发模式下，可写数据位于 [`data/`](data)；打包后会写入各平台的应用数据目录。
- 开发环境数据库默认是项目根目录下的 `Harmony.db`。
- 内置字体从 [`fonts/`](fonts) 加载；若缺失，会自动回退到系统字体。
- Linux 的系统媒体键依赖 MPRIS 和 QtDBus；Windows 可使用 `pynput`；macOS 目前主要回退到窗口聚焦时的快捷键。

## 界面截图

示例截图位于 [`screenshots/`](screenshots)。
