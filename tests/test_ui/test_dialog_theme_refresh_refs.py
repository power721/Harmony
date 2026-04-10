from unittest.mock import Mock

from system.theme import ThemeManager
from ui.dialogs.help_dialog import HelpDialog
from ui.dialogs.welcome_dialog import WelcomeDialog


def _init_theme():
    config = Mock()
    config.get.return_value = "dark"
    ThemeManager._instance = None
    return ThemeManager.instance(config)


def test_help_dialog_refresh_theme_uses_cached_label_refs(qtbot, monkeypatch):
    _init_theme()
    dialog = HelpDialog()
    qtbot.addWidget(dialog)

    monkeypatch.setattr(
        dialog,
        "findChildren",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("findChildren should not be used")),
    )

    dialog.refresh_theme()


def test_welcome_dialog_refresh_theme_uses_cached_icon_ref(qtbot, monkeypatch):
    _init_theme()
    dialog = WelcomeDialog(library_service=Mock())
    qtbot.addWidget(dialog)

    monkeypatch.setattr(
        dialog,
        "findChildren",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("findChildren should not be used")),
    )

    dialog.refresh_theme()
