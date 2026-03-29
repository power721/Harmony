"""Font loader for bundled fonts."""

import sys
from pathlib import Path
from typing import List

from PySide6.QtGui import QFontDatabase


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
        """Load bundled fonts into application font database."""
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

        for font_path, family in fonts_to_load:
            full_path = font_dir / font_path
            if full_path.exists():
                font_id = QFontDatabase.addApplicationFont(str(full_path))
                if font_id != -1:
                    self._font_ids.append(font_id)
                else:
                    print(f"Warning: Failed to load font: {full_path}")
            else:
                print(f"Warning: Font file not found: {full_path}")

        self._loaded = True

    def _get_font_dir(self) -> Path:
        """Get fonts directory path.

        Handles both development mode and PyInstaller bundle.
        """
        if getattr(sys, "frozen", False):
            # Running as PyInstaller bundle
            return Path(sys._MEIPASS) / "fonts"
        # Running in development mode
        return Path(__file__).parent.parent.parent / "fonts"

    def is_loaded(self) -> bool:
        """Check if fonts have been loaded."""
        return self._loaded

    def get_loaded_font_count(self) -> int:
        """Get number of successfully loaded fonts."""
        return len(self._font_ids)
