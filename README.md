# Harmony - Modern Music Player

一个使用 PySide6 构建的现代化音乐播放器，支持本地音乐和云盘音乐的无缝播放。

## 功能特性

### 🎵 本地音乐播放
- **音乐库管理** - 扫描和管理本地音乐文件
- **智能元数据提取** - 自动提取音频文件标签信息（标题、艺术家、专辑等）
- **专辑封面显示** - 自动抓取和显示专辑封面
- **多种音频格式** - 支持 MP3、FLAC、OGG、M4A、WAV、WMA 等格式
- **全文搜索** - 基于 FTS5 的快速歌曲搜索，支持模糊匹配和相关度排序

### ☁️ 云盘音乐集成
- **夸克网盘支持** - 通过二维码登录夸克网盘
- **在线浏览** - 直接浏览网盘中的音乐文件
- **智能下载** - 自动下载云盘音乐到本地缓存
- **断点续传** - 支持播放进度保存和恢复
- **混合播放** - 本地音乐和云盘音乐无缝切换

### 📋 播放列表管理
- **自定义播放列表** - 创建和管理播放列表
- **播放队列** - 实时查看和管理当前播放队列
- **队列拖拽排序** - 拖拽调整播放队列中的歌曲顺序
- **队列持久化** - 应用重启后恢复播放队列和顺序

### ⏯️ 播放控制
- **完整播放控制** - 播放/暂停/上一曲/下一曲
- **多种播放模式** - 顺序播放、随机播放、列表循环、单曲循环等
- **均衡器** - 内置音频均衡器和预设
- **进度控制** - 精确的播放进度控制

### 🎤 歌词功能
- **自动下载歌词** - 自动从网络获取歌词
- **LRC 格式支持** - 支持 .lrc 歌词文件解析
- **同步显示** - 歌词与播放进度同步显示
- **高级歌词窗口** - 支持滚屏和高亮显示

### 🖼️ 封面管理
- **自动封面获取** - 自动从网络获取专辑封面
- **手动下载封面** - 支持手动选择和下载专辑封面
- **多源支持** - 支持 iTunes、MusicBrainz、Last.fm 等封面来源
- **封面预览** - 下载前预览封面效果

### 🎨 现代化界面
- **Spotify 风格设计** - 简约现代的 UI 设计
- **迷你播放器** - 小巧的悬浮播放窗口，支持拖拽移动
- **系统托盘** - 最小化到系统托盘，后台播放
- **响应式布局** - 适配不同屏幕尺寸

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
pip install -r requirements.txt

# 运行应用
python main.py
```

### 依赖项

```
PySide6==6.6.0          # Qt6 GUI 框架
PySide6-Addons==6.6.0   # Qt6 多媒体支持
mutagen==1.47.0         # 音频元数据提取
requests==2.31.0        # HTTP 请求
beautifulsoup4==4.12.2  # 歌词爬取
lxml==5.1.0             # HTML 解析
pymediainfo==6.1.0      # 媒体信息提取（可选）
qrcode[pil]==8.2        # 二维码生成
```

## 使用说明

### 本地音乐

1. 首次运行时，点击左下角的"添加音乐"按钮
2. 选择包含音乐文件的文件夹
3. 音乐将被扫描并添加到音乐库
4. 点击歌曲即可播放

### 云盘音乐

1. 点击侧边栏的"云盘"选项卡
2. 点击"登录"按钮，显示二维码
3. 使用手机夸克网盘 APP 扫描二维码登录
4. 浏览云盘文件夹，点击音乐文件开始播放
5. 音乐将自动下载到本地缓存目录

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
- **数据库**: SQLite3
- **元数据提取**: mutagen, pymediainfo
- **网络请求**: requests
- **歌词解析**: BeautifulSoup4, lxml

### 核心架构

```
Harmony/
├── database/          # 数据库层
│   ├── manager.py     # 数据库管理器（线程安全）
│   └── models.py      # 数据模型（Track, Playlist, CloudAccount 等）
├── player/            # 播放引擎
│   ├── engine.py      # 底层播放引擎（QMediaPlayer 封装）
│   ├── playback_manager.py  # 统一播放控制器
│   ├── controller.py  # 传统播放控制器
│   ├── playlist_item.py     # 播放项抽象（本地/云盘统一接口）
│   └── equalizer.py   # 均衡器
├── services/          # 服务层
│   ├── metadata_service.py    # 元数据服务
│   ├── cover_service.py       # 封面服务
│   ├── lyrics_service.py      # 歌词服务
│   ├── lyrics_loader.py       # 歌词加载器（含 LRC 解析）
│   ├── quark_drive_service.py # 夸克网盘服务
│   └── cloud_download_service.py  # 云盘下载服务
├── ui/                # 用户界面
│   ├── main_window.py     # 主窗口
│   ├── library_view.py    # 音乐库视图
│   ├── playlist_view.py   # 播放列表视图
│   ├── queue_view.py      # 播放队列视图
│   ├── cloud_drive_view.py # 云盘视图
│   ├── player_controls.py # 播放控制器
│   ├── mini_player.py     # 迷你播放器
│   └── lyrics_widget.py   # 歌词显示组件
├── utils/             # 工具类
│   ├── event_bus.py       # 事件总线（单例模式）
│   ├── config.py          # 配置管理
│   ├── i18n.py            # 国际化
│   ├── global_hotkeys.py  # 全局快捷键
│   ├── lrc_parser.py      # LRC 解析器
│   └── helpers.py         # 辅助函数
├── translations/      # 翻译文件
│   ├── en.json           # 英文
│   └── zh.json           # 中文
└── main.py            # 应用入口
```

### 关键设计模式

- **EventBus 模式**: 集中式事件总线，解耦组件通信
- **单例模式**: EventBus 和 CloudDownloadService 使用单例
- **工厂模式**: PlaylistItem 使用工厂方法创建不同类型的播放项
- **线程本地存储**: DatabaseManager 使用 thread-local 确保线程安全
- **数据类模式**: 使用 `@dataclass` 定义数据模型

### 核心抽象

**PlaylistItem** - 统一的播放项抽象，支持本地和云盘文件：
- `is_local` / `is_cloud` - 判断来源类型
- `needs_download` - 云盘文件是否需要下载
- `from_track()` / `from_cloud_file()` - 工厂方法
- `to_play_queue_item()` - 转换为持久化模型

## 配置文件

### 数据库

- **位置**: `./music_player.db`（项目根目录）
- **表结构**:
  - `tracks` - 本地音乐库
  - `playlists` / `playlist_items` - 播放列表
  - `play_history` - 播放历史
  - `favorites` - 收藏
  - `cloud_accounts` - 云盘账号
  - `cloud_files` - 云盘文件缓存
  - `play_queue` - 持久化播放队列

### 配置文件

- **位置**: `~/.config/harmony_player/config.json`
- **内容**: 播放模式、音量、播放队列状态等

### 翻译文件

- **位置**: `translations/*.json`
- **支持语言**: 中文（zh）、英文（en）

## 开发

### 运行测试

```bash
# 运行测试
python -m pytest tests/

# 手动测试
python main.py
```

### 代码风格

项目遵循以下代码风格：
- 使用 PEP 8 规范
- 类型注解使用 `typing` 模块
- 数据类使用 `@dataclass` 装饰器
- 日志使用 Python logging 模块
- 日志格式: `'[%(levelname)s] %(name)s - %(message)s'`

### 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

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

### Q: 歌词无法显示？
A: 检查：
- 网络连接是否正常
- 歌词文件是否与音频文件同名（.lrc 格式）
- 尝试手动下载歌词

### Q: 应用崩溃后如何恢复播放状态？
A: 应用会自动保存播放队列和状态，重新启动后会自动恢复（不会自动播放）。

### Q: 迷你播放器窗口标题显示什么？
A: 播放时显示 "歌曲名 - 艺术家"，暂停/停止时显示应用名称。

## 许可证

本项目采用 MIT 许可证 - 详见 LICENSE 文件

## 致谢

- Qt 社区提供的优秀框架
- mutagen 提供的音频元数据处理
- 所有贡献者的支持

## 联系方式

- 项目主页: [GitHub Repository](https://github.com/power721/music-player)
- 问题反馈: [GitHub Issues](https://github.com/power721/music-player/issues)
