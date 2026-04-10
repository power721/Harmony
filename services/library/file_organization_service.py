"""
File organization service for moving music files to structured directories.
"""
import logging
import os
import shutil
from pathlib import Path
from typing import List, Dict

from utils.file_helpers import calculate_target_path, ensure_directory

logger = logging.getLogger(__name__)


class FileOrganizationService:
    """
    Service for organizing music files into structured directory layouts.
    """

    def __init__(self, track_repo, cloud_repo, event_bus, queue_repo=None):
        """
        Initialize file organization service.

        Args:
            track_repo: Track repository instance
            cloud_repo: Cloud repository instance
            event_bus: Global event bus
            queue_repo: Queue repository instance
        """
        self._track_repo = track_repo
        self._cloud_repo = cloud_repo
        self._event_bus = event_bus
        self._queue_repo = queue_repo

    def _get_all_lyrics_paths(self, audio_path: Path) -> List[Path]:
        """
        获取所有存在的歌词文件路径。

        Args:
            audio_path: 音频文件路径

        Returns:
            存在的歌词文件路径列表
        """
        lyrics_paths = []
        for ext in ['.yrc', '.qrc', '.lrc']:
            lyrics_path = audio_path.with_suffix(ext)
            if lyrics_path.exists():
                lyrics_paths.append(lyrics_path)
        return lyrics_paths

    def organize_tracks(self, track_ids: List[int], target_dir: str) -> Dict:
        """
        整理歌曲文件到目标目录。

        根据元数据将文件移动到结构化的目录中：
        - 有专辑: 歌手/专辑/歌曲.ext
        - 无专辑: 歌手/歌曲.ext
        - 无歌手: 直接在目标目录

        同时移动对应的歌词文件（.lrc, .yrc, .qrc，如果存在）。

        Args:
            track_ids: 要整理的歌曲 ID 列表
            target_dir: 目标根目录

        Returns:
            包含整理结果的字典:
            {
                'success': 成功数量,
                'failed': 失败数量,
                'errors': 错误信息列表
            }
        """
        results = {'success': 0, 'failed': 0, 'errors': []}
        target_path = Path(target_dir)

        if not target_path.exists():
            results['failed'] = len(track_ids)
            results['errors'].append(f"目标目录不存在: {target_dir}")
            return results
        if not target_path.is_dir():
            results['failed'] = len(track_ids)
            results['errors'].append(f"目标路径不是目录: {target_dir}")
            return results
        if not os.access(target_path, os.W_OK):
            results['failed'] = len(track_ids)
            results['errors'].append(f"目标目录不可写: {target_dir}")
            return results

        # Batch-load all tracks at once
        tracks = self._track_repo.get_by_ids(track_ids)
        track_map = {t.id: t for t in tracks}

        for track_id in track_ids:
            track = track_map.get(track_id)
            if not track:
                results['failed'] += 1
                results['errors'].append(f"Track ID {track_id}: 不存在")
                continue

            # Skip tracks without local path (online/cloud tracks)
            if not track.path or not track.path.strip():
                results['failed'] += 1
                results['errors'].append(f"{track.title}: 无本地文件（网络歌曲）")
                continue

            old_audio_path = Path(track.path)
            if not old_audio_path.exists():
                results['failed'] += 1
                results['errors'].append(f"{track.title}: 源文件不存在")
                continue

            # 计算新路径（音频和歌词）
            new_audio_path, new_lrc_path = calculate_target_path(track, target_dir)

            # 获取所有存在的歌词文件
            old_lyrics_paths = self._get_all_lyrics_paths(old_audio_path)

            # 确保目标目录存在
            if not ensure_directory(new_audio_path.parent):
                results['failed'] += 1
                results['errors'].append(f"{track.title}: 无法创建目录")
                continue

            # 处理文件名冲突
            final_audio_path = self._handle_conflict(new_audio_path)

            # 计算新的歌词文件路径
            new_lyrics_map = {}  # old_path -> new_path
            for old_lyrics_path in old_lyrics_paths:
                ext = old_lyrics_path.suffix
                new_lyrics_path = final_audio_path.parent / (final_audio_path.stem + ext)
                new_lyrics_map[old_lyrics_path] = new_lyrics_path

            # 移动音频文件
            try:
                shutil.move(str(old_audio_path), str(final_audio_path))
                logger.debug(f"移动音频文件: {old_audio_path} -> {final_audio_path}")
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"{track.title}: {str(e)}")
                continue

            # 移动歌词文件（如果存在）
            moved_lyrics = []
            for old_lyrics_path, new_lyrics_path in new_lyrics_map.items():
                try:
                    shutil.move(str(old_lyrics_path), str(new_lyrics_path))
                    moved_lyrics.append((old_lyrics_path, new_lyrics_path))
                    logger.debug(f"移动歌词文件: {old_lyrics_path} -> {new_lyrics_path}")
                except Exception as e:
                    # 歌词移动失败，回滚音频文件和已移动的歌词
                    try:
                        shutil.move(str(final_audio_path), str(old_audio_path))
                    except Exception:
                        pass
                    # 回滚已移动的歌词
                    for old_path, new_path in moved_lyrics:
                        try:
                            shutil.move(str(new_path), str(old_path))
                        except Exception:
                            pass
                    results['failed'] += 1
                    results['errors'].append(f"{track.title}: 歌词移动失败 {str(e)}")
                    break
            else:
                # 所有歌词移动成功

                # 更新数据库
                track.path = str(final_audio_path)
                if not self._track_repo.update(track):
                    # 回滚文件移动
                    rollback_failed = False
                    try:
                        shutil.move(str(final_audio_path), str(old_audio_path))
                        for old_path, new_path in moved_lyrics:
                            shutil.move(str(new_path), str(old_path))
                    except Exception as exc:
                        rollback_failed = True
                        logger.error(f"文件回滚失败: {exc}", exc_info=True)
                    results['failed'] += 1
                    message = f"{track.title}: 数据库更新失败"
                    if rollback_failed:
                        message += "（文件回滚失败）"
                    results['errors'].append(message)
                    continue

                # 更新 play_queue 和 cloud_files 中的路径
                self._update_paths_after_move(track_id, str(final_audio_path), track.cloud_file_id)

                results['success'] += 1
                logger.info(f"成功整理: {track.title} -> {final_audio_path}")

        # 发出事件
        self._event_bus.tracks_organized.emit(results)
        return results

    def _update_paths_after_move(self, track_id: int, new_path: str, cloud_file_id: str = None):
        """
        更新播放队列和云文件表中的路径。

        Args:
            track_id: 歌曲ID
            new_path: 新的路径
            cloud_file_id: 云文件ID（如果是云下载文件）
        """
        try:
            # 更新 play_queue 表
            self._queue_repo.update_local_path(track_id, new_path)
            logger.debug(f"更新 play_queue: track_id={track_id}, 新路径={new_path}")

            # 更新 cloud_files 表（如果是云下载文件）
            if cloud_file_id:
                # Get account_id for cloud_file_id using repository
                account_id = self._cloud_repo.get_account_id_by_file_id(cloud_file_id)
                if account_id:
                    self._cloud_repo.update_file_local_path(cloud_file_id, account_id, new_path)
                    logger.debug(f"更新 cloud_files: file_id={cloud_file_id}, 新路径={new_path}")
        except Exception as e:
            logger.error(f"更新路径失败: {e}")

    def _handle_conflict(self, path: Path) -> Path:
        """
        处理文件名冲突，自动添加序号。

        例如: song.mp3 -> song (2).mp3

        Args:
            path: 目标路径

        Returns:
            不冲突的路径
        """
        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        parent = path.parent

        counter = 2
        while True:
            new_path = parent / f"{stem} ({counter}){suffix}"
            if not new_path.exists():
                return new_path
            counter += 1

    def preview_organization(self, track_ids: List[int], target_dir: str) -> List[Dict]:
        """
        预览整理结果，返回新旧路径列表。

        Args:
            track_ids: 要整理的歌曲 ID 列表
            target_dir: 目标根目录

        Returns:
            预览信息列表，每项包含:
            {
                'track': Track 对象,
                'old_audio_path': 旧音频路径,
                'new_audio_path': 新音频路径,
                'has_lyrics': 是否有歌词文件,
                'old_lrc_path': 旧歌词路径（如果有）,
                'new_lrc_path': 新歌词路径
            }
        """
        previews = []
        for track_id in track_ids:
            track = self._track_repo.get_by_id(track_id)
            if track:
                # Skip tracks without local path (online/cloud tracks)
                if not track.path or not track.path.strip():
                    continue

                new_audio_path, new_lrc_path = calculate_target_path(track, target_dir)
                old_lyrics_paths = self._get_all_lyrics_paths(Path(track.path))

                # Use first lyrics path for backwards compatibility
                old_lrc_path = old_lyrics_paths[0] if old_lyrics_paths else Path(track.path).with_suffix('.lrc')

                previews.append({
                    'track': track,
                    'old_audio_path': track.path,
                    'new_audio_path': str(new_audio_path),
                    'has_lyrics': len(old_lyrics_paths) > 0,
                    'old_lrc_path': str(old_lrc_path) if old_lyrics_paths else None,
                    'new_lrc_path': str(new_lrc_path),
                })
        return previews
