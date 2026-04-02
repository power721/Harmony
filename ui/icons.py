"""
Icon management using SVG icons with dynamic coloring.

This module provides cross-platform consistent icons using SVG files
instead of emojis which may not display correctly on all platforms.
"""
import logging
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QPushButton

logger = logging.getLogger(__name__)

# Icons directory path
ICONS_DIR = Path(__file__).parent.parent / "icons"

# Icon cache: key = f"{icon_name}_{color}_{size}", value = QIcon
_ICON_CACHE: dict = {}


# Icon colors for different states
class IconColor:
    """Icon colors for different states - these are defaults, actual colors come from theme."""
    DEFAULT = "#c0c0c0"  # Fallback
    HOVER = "#1db954"  # Fallback
    ACTIVE = "#000000"  # Black on green background
    DISABLED = "#505050"  # Fallback

    @classmethod
    def get_colors_from_theme(cls, theme):
        """Get icon colors from current theme."""
        return {
            'default': theme.text_secondary,
            'hover': theme.highlight,
            'active': '#000000',  # Black for contrast on highlight bg
            'disabled': theme.border,
        }


class IconName:
    """SVG icon file names."""
    # Navigation
    MUSIC = "music.svg"
    COMPACT_DISC = "compact-disc.svg"
    MICROPHONE = "microphone.svg"
    CLOUD = "cloud.svg"
    LIST = "list.svg"
    GRID = "grid.svg"
    QUEUE = "queue.svg"
    STAR = "star.svg"
    CLOCK = "clock.svg"
    ALARM = "alarm.svg"

    # Actions
    PLAY = "play.svg"
    PAUSE = "pause.svg"
    NEXT = "next.svg"
    PREVIOUS = "previous.svg"
    SHUFFLE = "shuffle.svg"
    REPEAT = "repeat.svg"
    REPEAT_ONCE = "repeat_once.svg"

    # Volume
    VOLUME_HIGH = "volume-high.svg"
    VOLUME_LOW = "volume-low.svg"
    VOLUME_OFF = "volume-off.svg"

    # Files & Folders
    FOLDER = "folder.svg"

    # Status
    CHECK = "check.svg"
    TIMES = "times.svg"
    STAR_FILLED = "star-filled.svg"
    STAR_OUTLINE = "star-outline.svg"
    HEART_FILLED = "heart-filled.svg"
    HEART_OUTLINE = "heart-outline.svg"

    # Settings & Tools
    ROBOT = "robot.svg"
    EQUALIZER = "equalizer.svg"

    # UI
    GLOBE = "globe.svg"
    INFO = "info.svg"
    TRASH = "trash.svg"
    USER = "user.svg"
    LIGHTBULB = "lightbulb.svg"

    # Window controls
    MINIMIZE = "minimize.svg"
    MAXIMIZE = "maximize.svg"

    # Dialog icons
    WARNING = "warning.svg"
    CRITICAL = "critical.svg"


def _colorize_svg(svg_content: bytes, color: str) -> bytes:
    """
    Replace fill and stroke color in SVG content.
    For icons with background (multiple paths), only keep the foreground paths.

    Args:
        svg_content: Original SVG bytes
        color: New color (hex format like "#ffffff")

    Returns:
        Modified SVG bytes
    """
    import re
    svg_str = svg_content.decode('utf-8')

    # Check if this is a multi-path icon with background (common pattern: background + icon)
    # If there are exactly 2 paths and one fills the entire viewBox (background), remove it
    paths = re.findall(r'<path[^>]*>', svg_str)
    if len(paths) == 2:
        # Check if first path is a background (fills entire area: M36 32... or M0 0...)
        first_path_d = re.search(r'<path[^>]*d="([^"]*)"', paths[0])
        if first_path_d:
            d = first_path_d.group(1)
            # Background typically starts with M36 or M0 and fills the entire viewBox
            if d.startswith('M36') or d.startswith('M0 0'):
                # Remove the background path
                svg_str = svg_str.replace(paths[0], '')

    # Replace fill="#xxx" or fill='xxx', but keep fill="none"
    svg_str = re.sub(r'fill="(?!none")[^"]*"', f'fill="{color}"', svg_str)
    svg_str = re.sub(r"fill='(?!none')[^']*'", f"fill='{color}'", svg_str)
    # Replace stroke="#xxx" or stroke='xxx'
    svg_str = re.sub(r'stroke="(?!none")[^"]*"', f'stroke="{color}"', svg_str)
    svg_str = re.sub(r"stroke='(?!none')[^']*'", f"stroke='{color}'", svg_str)
    return svg_str.encode('utf-8')


def get_icon(icon_name: str, color: str | None = IconColor.DEFAULT, size: int = 24) -> QIcon:
    """
    Get QIcon from SVG file with specified color.

    Args:
        icon_name: Icon file name from IconName class
        color: Color for the icon (hex format)
        size: Icon size in pixels

    Returns:
        QIcon object, or empty QIcon if file not found
    """
    # Check cache first
    cache_key = f"{icon_name}_{color}_{size}"
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    icon_path = ICONS_DIR / icon_name
    if not icon_path.exists():
        logger.warning(f"Icon file not found: {icon_path}")
        return QIcon()

    try:
        # Read SVG content
        with open(icon_path, 'rb') as f:
            svg_content = f.read()

        # Colorize SVG only if color is specified
        if color:
            colored_svg = _colorize_svg(svg_content, color)
        else:
            colored_svg = svg_content

        # Render to pixmap
        renderer = QSvgRenderer(colored_svg)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        icon = QIcon(pixmap)
        _ICON_CACHE[cache_key] = icon
        return icon

    except Exception as e:
        logger.error(f"Error loading icon {icon_name}: {e}")
        return QIcon()


def get_pixmap(icon_name: str, color: str = IconColor.DEFAULT, size: int = 24) -> QPixmap:
    """
    Get QPixmap from SVG file with specified color.

    Args:
        icon_name: Icon file name from IconName class
        color: Color for the icon (hex format)
        size: Icon size in pixels

    Returns:
        QPixmap object
    """
    icon = get_icon(icon_name, color, size)
    return icon.pixmap(QSize(size, size))


class IconButton(QPushButton):
    """
    QPushButton with SVG icon that changes color based on state.

    States:
    - Normal: Default color
    - Hover: Green color
    - Checked: White color (on green background)
    - Disabled: Gray color
    """

    def __init__(self, icon_name: str, text: str = "", parent=None, size: int = 24):
        super().__init__(text, parent)
        self._icon_name = icon_name
        self._icon_size = size

        # Get colors from theme if available
        try:
            from system.theme import ThemeManager
            tm = ThemeManager.instance()
            colors = IconColor.get_colors_from_theme(tm.current_theme)
            self._default_color = colors['default']
            self._hover_color = colors['hover']
            self._active_color = colors['active']
            self._disabled_color = colors['disabled']
        except Exception:
            # Fallback to defaults
            self._default_color = IconColor.DEFAULT
            self._hover_color = IconColor.HOVER
            self._active_color = IconColor.ACTIVE
            self._disabled_color = IconColor.DISABLED

        self._update_icon()
        self.setIconSize(QSize(size, size))

        # Connect toggled signal to update icon on state change
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool):
        """Handle toggled signal - update icon color."""
        if checked:
            self._update_icon(self._active_color)
        else:
            self._update_icon(self._default_color)

    def _update_icon(self, color: str = None):
        """Update icon with specified color."""
        if color is None:
            if not self.isEnabled():
                color = self._disabled_color
            elif self.isChecked():
                color = self._active_color
            else:
                color = self._default_color

        icon = get_icon(self._icon_name, color, self._icon_size)
        self.setIcon(icon)

    def set_icon_color(self, default: str = None, hover: str = None, active: str = None):
        """Set custom colors for different states."""
        if default:
            self._default_color = default
        if hover:
            self._hover_color = hover
        if active:
            self._active_color = active
        self._update_icon()

    def enterEvent(self, event):
        """Handle mouse enter - change to hover color."""
        super().enterEvent(event)
        if not self.isChecked():
            self._update_icon(self._hover_color)

    def leaveEvent(self, event):
        """Handle mouse leave - restore default color."""
        super().leaveEvent(event)
        if not self.isChecked():
            self._update_icon(self._default_color)

    def setEnabled(self, enabled: bool):
        """Override to update icon on enabled change."""
        super().setEnabled(enabled)
        self._update_icon()


def icon_button(icon_name: str, text: str = "", size: int = 24, parent=None) -> IconButton:
    """
    Create an IconButton with icon and optional text.

    Args:
        icon_name: Icon file name from IconName class
        text: Optional text to display after icon
        size: Icon size in pixels
        parent: Parent widget

    Returns:
        IconButton with state-aware icon
    """
    return IconButton(icon_name, text, parent, size)


def set_button_icon(button: QPushButton, icon_name: str, size: int = 24, color: str = IconColor.DEFAULT):
    """
    Set icon on an existing button with specified color.

    Args:
        button: QPushButton to set icon on
        icon_name: Icon file name from IconName class
        size: Icon size in pixels
        color: Icon color
    """
    icon = get_icon(icon_name, color, size)
    button.setIcon(icon)
    button.setIconSize(QSize(size, size))


def get_icon_path(icon_name: str) -> str:
    """
    Get full path to icon file.

    Args:
        icon_name: Icon file name from IconName class

    Returns:
        Full path string to the icon file
    """
    return str(ICONS_DIR / icon_name)
