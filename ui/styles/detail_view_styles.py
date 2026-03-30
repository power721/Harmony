"""
Common style generators for detail view pages.
Provides consistent styling across artist, album, and genre detail pages.
"""


def get_scroll_area_style(theme) -> str:
    """Get scroll area stylesheet."""
    return f"""
        QScrollArea {{
            background-color: {theme.background};
            border: none;
        }}
        QScrollBar:vertical {{
            background-color: {theme.background};
            width: 12px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {theme.background_alt};
            border-radius: 6px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {theme.background_hover};
        }}
    """


def get_header_style(theme) -> str:
    """Get header gradient stylesheet."""
    return f"""
        QFrame {{
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 {theme.highlight}, stop:1 {theme.background}
            );
        }}
    """


def get_cover_style(theme, border_radius: str = "8px") -> str:
    """Get cover label stylesheet.

    Args:
        theme: Theme object with color properties
        border_radius: Border radius string (e.g., "8px" for album/genre, "100px" for artist)
    """
    return f"""
        QLabel {{
            background-color: {theme.background_hover};
            border-radius: {border_radius};
        }}
    """


def get_type_label_style(theme) -> str:
    """Get type label stylesheet (e.g., 'Artist', 'Album', 'Genre')."""
    return f"""
        QLabel {{
            color: {theme.text_secondary};
            font-size: 12px;
            font-weight: bold;
        }}
    """


def get_name_label_style(theme) -> str:
    """Get name label stylesheet (main title)."""
    return f"""
        QLabel {{
            color: {theme.text};
            font-size: 48px;
            font-weight: bold;
        }}
    """


def get_info_label_style(theme) -> str:
    """Get info label stylesheet (stats, metadata)."""
    return f"""
        QLabel {{
            color: {theme.text_secondary};
            font-size: 14px;
        }}
    """


def get_play_button_style(theme) -> str:
    """Get play button stylesheet."""
    return f"""
        QPushButton {{
            background-color: {theme.highlight};
            color: {theme.background};
            border: none;
            border-radius: 18px;
            font-size: 14px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {theme.highlight_hover};
        }}
    """


def get_outline_button_style(theme) -> str:
    """Get outline button stylesheet (shuffle, back buttons)."""
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {theme.text_secondary};
            border: 1px solid {theme.border};
            border-radius: 18px;
            font-size: 14px;
        }}
        QPushButton:hover {{
            color: {theme.text};
            border-color: {theme.text};
        }}
    """


def get_section_title_style(theme) -> str:
    """Get section title stylesheet (e.g., 'Albums', 'All Tracks')."""
    return f"""
        QLabel {{
            color: {theme.highlight};
            font-size: 24px;
            font-weight: bold;
            padding: 10px;
        }}
    """


def get_tracks_table_style(theme) -> str:
    """Get tracks table stylesheet."""
    return f"""
        QTableWidget {{
            background-color: {theme.background};
            border: none;
            border-radius: 8px;
            gridline-color: {theme.background_hover};
        }}
        QTableWidget::item {{
            padding: 12px 8px;
            color: {theme.text};
            border: none;
            border-bottom: 1px solid {theme.background_hover};
        }}
        QTableWidget::item:alternate {{
            background-color: {theme.background_alt};
        }}
        QTableWidget::item:!alternate {{
            background-color: {theme.background};
        }}
        QTableWidget::item:selected {{
            background-color: {theme.highlight};
            color: {theme.background};
            font-weight: 500;
        }}
        QTableWidget::item:selected:!alternate {{
            background-color: {theme.highlight};
        }}
        QTableWidget::item:selected:alternate {{
            background-color: {theme.highlight_hover};
        }}
        QTableWidget::item:hover {{
            background-color: {theme.background_hover};
        }}
        QTableWidget::item:selected:hover {{
            background-color: {theme.highlight_hover};
        }}
        QTableWidget QHeaderView::section {{
            background-color: {theme.background_hover};
            color: {theme.highlight};
            padding: 14px 12px;
            border: none;
            border-bottom: 2px solid {theme.highlight};
            font-weight: bold;
            font-size: 13px;
            letter-spacing: 0.5px;
        }}
        QTableWidget QTableCornerButton::section {{
            background-color: {theme.background_hover};
            border: none;
            border-bottom: 2px solid {theme.highlight};
        }}
        QTableWidget QScrollBar:vertical {{
            background-color: {theme.background};
            width: 12px;
            border-radius: 6px;
        }}
        QTableWidget QScrollBar::handle:vertical {{
            background-color: {theme.border};
            border-radius: 6px;
            min-height: 40px;
        }}
        QTableWidget QScrollBar::handle:vertical:hover {{
            background-color: {theme.background_hover};
        }}
    """


def get_progress_bar_style(theme) -> str:
    """Get progress bar stylesheet (loading indicator)."""
    return f"""
        QProgressBar {{
            background-color: {theme.background_hover};
            border: none;
            border-radius: 2px;
        }}
        QProgressBar::chunk {{
            background-color: {theme.highlight};
            border-radius: 2px;
        }}
    """


def get_loading_label_style(theme) -> str:
    """Get loading label stylesheet."""
    return f"color: {theme.text_secondary}; font-size: 14px;"
