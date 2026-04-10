"""
File utility functions for file organization.
"""
import os
import re
from pathlib import Path
from domain.track import Track

# Pre-compiled regex patterns for filename sanitization
_RE_PATH_SEP = re.compile(r'[\\/]')
_RE_INVALID_CHARS = re.compile(r'[<>:"|?*]')
_RE_WHITESPACE = re.compile(r'\s+')


def sanitize_filename(name: str) -> str:
    """
    清理文件名中的非法字符。

    Args:
        name: 原始文件名

    Returns:
        清理后的文件名
    """
    if not name:
        return "unnamed"

    # 替换路径分隔符为 &
    cleaned = _RE_PATH_SEP.sub('&', name)
    # 移除其他非法字符
    cleaned = _RE_INVALID_CHARS.sub('', cleaned)
    # 清理多余空格和点
    cleaned = _RE_WHITESPACE.sub(' ', cleaned).strip('. ')
    return cleaned or "unnamed"


def calculate_target_path(track: Track, target_dir: str) -> tuple[Path, Path]:
    """
    计算目标路径（音频和歌词）。

    根据歌曲的元数据（歌手、专辑）计算整理后的目录结构：
    - 有专辑和歌手: 歌手/专辑/歌曲.ext
    - 只有歌手: 歌手/歌曲.ext
    - 无歌手: 歌曲.ext（直接在目标目录）

    Args:
        track: 歌曲 Track 对象
        target_dir: 目标根目录

    Returns:
        (audio_path, lyrics_path) 元组

    Raises:
        ValueError: 如果 track.path 为空或无效
    """
    # Validate track has a local path
    if not track.path or not track.path.strip():
        raise ValueError(f"Track '{track.title}' has no local path")

    target_path = Path(target_dir)
    if not target_path.exists():
        raise ValueError(f"target directory does not exist: {target_dir}")
    if not target_path.is_dir():
        raise ValueError(f"target directory is not a directory: {target_dir}")
    if not os.access(target_path, os.W_OK):
        raise ValueError(f"target directory is not writable: {target_dir}")

    track_path = Path(track.path)
    ext = track_path.suffix
    title = sanitize_filename(track.title or track_path.stem)

    # 规则1: 有专辑和歌手 → 歌手/专辑/歌曲
    if track.album and track.artist:
        artist = sanitize_filename(track.artist)
        album = sanitize_filename(track.album)
        base = target_path / artist / album / title
        return base.with_suffix(ext), base.with_suffix('.lrc')

    # 规则2: 只有歌手 → 歌手/歌曲
    if track.artist:
        artist = sanitize_filename(track.artist)
        base = target_path / artist / title
        return base.with_suffix(ext), base.with_suffix('.lrc')

    # 规则3: 无歌手 → 直接在目标目录
    base = target_path / title
    return base.with_suffix(ext), base.with_suffix('.lrc')


def ensure_directory(path: Path) -> bool:
    """
    确保目录存在，如果不存在则创建。

    Args:
        path: 目录路径

    Returns:
        True if directory exists or was created successfully
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False


def get_lyrics_path(audio_path: str) -> Path:
    """
    获取歌词文件路径。

    检查 .yrc, .qrc, .lrc 扩展名，返回第一个存在的文件路径。
    如果都不存在，默认返回 .lrc 路径。

    Args:
        audio_path: 音频文件路径

    Returns:
        对应的歌词文件路径
    """
    audio = Path(audio_path)

    # Check for existing lyrics files in priority order
    for ext in ['.yrc', '.qrc', '.lrc']:
        lyrics_path = audio.with_suffix(ext)
        if lyrics_path.exists():
            return lyrics_path

    # Default to .lrc if no lyrics file exists
    return audio.with_suffix('.lrc')
