"""Font loader for bundled fonts."""

import sys
import logging
from pathlib import Path
from typing import List

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
            ("Inter/Inter-Regular.ttf", "Inter"),
            ("Inter/Inter-Medium.ttf", "Inter"),
            ("Inter/Inter-Bold.ttf", "Inter"),
            ("NotoSansSC/NotoSansSC-Regular.ttf", "Noto Sans SC"),
            ("NotoSansSC/NotoSansSC-Medium.ttf", "Noto Sans SC"),
            ("NotoSansSC/NotoSansSC-Bold.ttf", "Noto Sans SC"),
            ("NotoColorEmoji/NotoColorEmoji.ttf", "Noto Color Emoji"),
        ]

        loaded_count = 0
        for font_path, family in fonts_to_load:
            full_path = font_dir / font_path
            if full_path.exists():
                font_id = QFontDatabase.addApplicationFont(str(full_path))
                if font_id != -1:
                    self._font_ids.append(font_id)
                    loaded_count += 1
                    logger.debug(f"Loaded font: {family} from {full_path}")
                else:
                    logger.warning(f"Failed to load font: {full_path}")
            else:
                logger.debug(f"Font file not found: {full_path}")

        if loaded_count > 0:
            logger.info(f"Loaded {loaded_count}/{len(fonts_to_load)} bundled fonts")
        else:
            logger.info("No bundled fonts found, using system fonts")

        self._loaded = True

    def _get_font_dir(self) -> Path:
        """Get fonts directory path.

        Handles development mode, PyInstaller bundle, and AppImage.
        """
        if getattr(sys, "frozen", False):
            # Running as PyInstaller bundle or AppImage
            # PyInstaller sets sys._MEIPASS to the temp extraction directory
            # AppImage doesn't set _MEIPASS, uses _internal subdirectory
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                return Path(meipass) / "fonts"
            else:
                # AppImage case: fonts are in _internal/fonts relative to executable
                executable_dir = Path(sys.executable).parent
                return executable_dir / "_internal" / "fonts"
        # Running in development mode
        return Path(__file__).parent.parent.parent / "fonts"

    def is_loaded(self) -> bool:
        """Check if fonts have been loaded."""
        return self._loaded

    def get_loaded_font_count(self) -> int:
        """Get number of successfully loaded fonts."""
        return len(self._font_ids)
