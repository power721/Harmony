"""Reusable cover loading helpers for widgets and windows."""

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


class CoverLoader:
    """Shared helpers for resolving cover paths and loading scaled pixmaps."""

    @staticmethod
    def resolve_track_cover_path(track_dict: dict, cover_service, fallback_loader, logger=None) -> str:
        cover_path = track_dict.get("cover_path")
        if cover_path and Path(cover_path).exists():
            return cover_path

        source = track_dict.get("source", "") or track_dict.get("source_type", "")
        cloud_file_id = track_dict.get("cloud_file_id", "")
        provider_id = track_dict.get("online_provider_id")
        is_online = source in ("online", "ONLINE")
        if is_online and cloud_file_id and cover_service:
            try:
                online_cover = cover_service.get_online_cover(
                    song_mid=cloud_file_id,
                    album_mid=None,
                    artist=track_dict.get("artist", ""),
                    title=track_dict.get("title", ""),
                    provider_id=provider_id,
                )
                if online_cover:
                    return online_cover
            except Exception as exc:
                (logger or logging.getLogger(__name__)).debug("Online cover load failed: %s", exc)

        path = track_dict.get("path", "")
        title = track_dict.get("title", "")
        artist = track_dict.get("artist", "")
        album = track_dict.get("album", "")
        needs_download = track_dict.get("needs_download", False)
        is_cloud = track_dict.get("is_cloud", False)
        skip_online = needs_download or (is_cloud and not path)
        return fallback_loader(path, title, artist, album, skip_online=skip_online) or ""

    @staticmethod
    def load_pixmap(cover_path: str) -> QPixmap | None:
        pixmap = QPixmap(cover_path)
        return None if pixmap.isNull() else pixmap

    @staticmethod
    def scaled_pixmap(pixmap: QPixmap, width: int, height: int) -> QPixmap:
        return pixmap.scaled(width, height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

    @classmethod
    def load_scaled_pixmap(cls, cover_path: str, width: int, height: int) -> QPixmap | None:
        pixmap = cls.load_pixmap(cover_path)
        if pixmap is None:
            return None
        return cls.scaled_pixmap(pixmap, width, height)

    @classmethod
    def pixmap_from_bytes(cls, image_data: bytes, width: int, height: int) -> QPixmap | None:
        pixmap = QPixmap()
        if not pixmap.loadFromData(image_data):
            return None
        return cls.scaled_pixmap(pixmap, width, height)
