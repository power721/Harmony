"""Font loader for bundled fonts."""

import logging
from pathlib import Path
from typing import List

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QFontDatabase

logger = logging.getLogger(__name__)


class FontLoader:
    """Singleton font loader for bundled fonts."""

    _instance = None
    _loaded = False
    _font_ids: List[int] = []

    @classmethod
    def instance(cls) -> "FontLoader":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_fonts(self) -> None:
        """Load bundled fonts into application font database.

        If font files are not found, the application will fall back to
        system fonts. This allows the app to work in development without
        downloading fonts, though the appearance may vary across platforms.
        """
        if self._loaded:
            return

        font_dir = self._get_font_dir()
        fonts_to_load = [
            ("Inter-Regular.ttf", "Inter"),
            ("Inter-Medium.ttf", "Inter"),
            ("Inter-Bold.ttf", "Inter"),
            ("NotoSansSC-Regular.ttf", "Noto Sans SC"),
            ("NotoSansSC-Medium.ttf", "Noto Sans SC"),
            ("NotoSansSC-Bold.ttf", "Noto Sans SC"),
            ("NotoColorEmoji.ttf", "Noto Color Emoji"),
        ]

        loaded_count = 0
        for font_path, family in fonts_to_load:
            full_path = font_dir / font_path
            if full_path.exists():
                try:
                    font_id = QFontDatabase.addApplicationFont(str(full_path))
                    if font_id != -1:
                        self._font_ids.append(font_id)
                        loaded_count += 1
                        logger.debug(f"Loaded font: {family} from {full_path}")
                    else:
                        logger.warning(f"Failed to load font: {full_path}")
                except Exception as e:
                    logger.warning(f"Error loading font {full_path}: {e}")
            else:
                logger.debug(f"Font file not found: {full_path}")

        if loaded_count > 0:
            logger.info(f"Loaded {loaded_count}/{len(fonts_to_load)} bundled fonts")
        else:
            logger.info("No bundled fonts found, using system fonts")

        self._loaded = True

    def _get_font_dir(self) -> Path:
        """Get fonts directory path.

        Uses Qt's applicationDirPath() which works correctly for:
        - PyInstaller onefile/onedir
        - AppImage
        - All platforms (Linux, macOS, Windows)

        For development mode, falls back to project root fonts directory.
        """
        base_path = QCoreApplication.applicationDirPath()
        font_dir = Path(base_path) / "fonts"

        # In development mode, applicationDirPath() returns Python interpreter dir
        # Check if fonts directory exists, if not, use project root
        if not font_dir.exists():
            # Development mode: fonts are in project root
            font_dir = Path(__file__).parent.parent.parent / "fonts"

        return font_dir

    def is_loaded(self) -> bool:
        """Check if fonts have been loaded."""
        return self._loaded

    def get_loaded_font_count(self) -> int:
        """Get number of successfully loaded fonts."""
        return len(self._font_ids)
