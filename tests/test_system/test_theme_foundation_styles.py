from unittest.mock import Mock

from system.theme import ThemeManager


def _build_theme_manager():
    config = Mock()
    config.get.return_value = "dark"
    ThemeManager._instance = None
    return ThemeManager.instance(config)


def test_theme_manager_exposes_foundation_popup_helpers():
    tm = _build_theme_manager()

    completer_qss = tm.get_themed_completer_popup_style()
    popup_qss = tm.get_themed_popup_surface_style()

    assert "#121212" in completer_qss or "#282828" in completer_qss
    assert "QListView" in completer_qss
    assert "popupSurface" in popup_qss
    assert tm.current_theme.highlight in completer_qss


def test_theme_manager_global_stylesheet_covers_foundation_selectors(qapp):
    tm = _build_theme_manager()

    tm.apply_global_stylesheet()
    stylesheet = qapp.styleSheet()

    assert "QLineEdit" in stylesheet
    assert "QCheckBox::indicator" in stylesheet
    assert "QGroupBox" in stylesheet
    assert "QComboBox" in stylesheet
    assert "QDialog[shell=\"true\"]" in stylesheet
    assert "QWidget#dialogTitleBar" in stylesheet


def test_theme_manager_global_stylesheet_includes_wrapper_variants(qapp):
    tm = _build_theme_manager()

    tm.apply_global_stylesheet()
    stylesheet = qapp.styleSheet()

    assert "QPushButton[role=\"primary\"]" in stylesheet
    assert "QLineEdit[variant=\"search\"]" in stylesheet
    assert "QComboBox[compact=\"true\"]" in stylesheet
    assert "QWidget#titleBar" in stylesheet
    assert "QPushButton#winBtn" in stylesheet
    assert "QPushButton#dialogCloseBtn" in stylesheet
