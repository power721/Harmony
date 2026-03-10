# Harmony - Modern Music Player

一个使用 PySide6 构建的现代化音乐播放器。

## 功能特性

- 🎵 **音乐库管理** - 扫描和管理本地音乐文件
- 🎵 **网盘音乐库** - 网盘音乐文件下载播放
- 📋 **播放列表** - 创建和管理自定义播放列表
- ⏯️ **播放控制** - 完整的播放控制（播放/暂停/上一曲/下一曲）
- 📜 **播放历史** - 自动记录播放历史
- ⭐ **收藏功能** - 收藏喜爱的歌曲
- 🎤 **歌词显示** - 自动加载和同步显示歌词
- 🖼️ **封面显示** - 自动抓取和显示专辑封面
- 🎨 **现代 UI** - 类似 Spotify/Apple Music 的简约设计
- ⌨️ **全局快捷键** - 支持系统级媒体键控制
- 🪟 **迷你模式** - 小巧的悬浮播放窗口
- 自动下载歌词
- 支持播放模式：顺序播放、随机播放、列表循环、单曲循环
- 重启恢复播放

## 安装

```bash
# 克隆仓库
git clone <repository-url>
cd music-player

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

## 依赖项

- Python 3.10+
- PySide6
- mutagen
- requests
- beautifulsoup4

## 使用说明

1. 首次运行时，点击左下角的"添加音乐"按钮选择音乐文件夹
2. 音乐将被扫描并添加到音乐库
3. 点击歌曲即可播放
4. 使用底部控制栏控制播放

## 技术栈

- **GUI**: PySide6 (Qt6)
- **音频**: Qt Multimedia (QMediaPlayer)
- **数据库**: SQLite3
- **元数据**: mutagen

## 许可证

MIT License
