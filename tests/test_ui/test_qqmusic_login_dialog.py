from unittest.mock import Mock

from plugins.builtin.qqmusic.lib.i18n import t
from plugins.builtin.qqmusic.lib.login_dialog import QQMusicLoginDialog
from tests.test_plugins.qqmusic_test_context import bind_test_context


def _context():
    theme_manager = Mock()
    theme = Mock(
        background="#101010",
        background_alt="#1a1a1a",
        background_hover="#202020",
        text="#ffffff",
        text_secondary="#999999",
        highlight="#1db954",
        border="#404040",
    )
    theme_manager.get_qss.side_effect = lambda template: template
    theme_manager.current_theme = theme
    theme_manager.register_widget = Mock()
    return bind_test_context(theme_manager=theme_manager)


def test_login_dialog_defaults_to_qr_mode(qtbot, monkeypatch):
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.login_dialog.QQMusicLoginDialog._start_login",
        lambda self: None,
    )
    dialog = QQMusicLoginDialog(_context())
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog._login_mode == "qr"
    assert dialog._qr_mode_btn.isChecked() is True
    assert not dialog._qr_panel.isHidden()
    assert dialog._phone_panel.isHidden()


def test_login_dialog_can_switch_to_phone_mode(qtbot, monkeypatch):
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.login_dialog.QQMusicLoginDialog._start_login",
        lambda self: None,
    )
    dialog = QQMusicLoginDialog(_context())
    qtbot.addWidget(dialog)
    dialog.show()

    dialog._phone_mode_btn.click()

    assert dialog._login_mode == "phone"
    assert not dialog._phone_panel.isHidden()
    assert dialog._qr_panel.isHidden()
    assert dialog._country_code_label.text() == "+86"


def test_phone_login_rejects_invalid_phone_inline(qtbot, monkeypatch):
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.login_dialog.QQMusicLoginDialog._start_login",
        lambda self: None,
    )
    dialog = QQMusicLoginDialog(_context())
    qtbot.addWidget(dialog)
    dialog.show()
    dialog._phone_mode_btn.click()
    dialog._phone_input.setText("123")

    dialog._send_phone_auth_code()

    assert dialog._phone_status_label.text() == t("qqmusic_phone_invalid")


def test_phone_login_emits_credentials_on_success(qtbot, monkeypatch):
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.login_dialog.QQMusicLoginDialog._start_login",
        lambda self: None,
    )
    context = _context()
    dialog = QQMusicLoginDialog(context)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog._phone_mode_btn.click()
    dialog._phone_input.setText("13000000000")
    dialog._phone_code_input.setText("123456")
    dialog._phone_client = Mock()
    dialog._phone_client.phone_authorize.return_value = {
        "musicid": "1",
        "musickey": "secret",
        "nick": "Tester",
    }
    captured = {}
    dialog.credentials_obtained.connect(lambda credential: captured.setdefault("credential", credential))

    dialog._submit_phone_login()

    assert captured["credential"]["musicid"] == "1"
    assert context.settings.get("credential", None)["musickey"] == "secret"


def test_phone_login_shows_frequency_error_inline(qtbot, monkeypatch):
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.login_dialog.QQMusicLoginDialog._start_login",
        lambda self: None,
    )
    dialog = QQMusicLoginDialog(_context())
    qtbot.addWidget(dialog)
    dialog.show()
    dialog._phone_mode_btn.click()
    dialog._phone_input.setText("13000000000")
    dialog._phone_client = Mock()
    dialog._phone_client.send_phone_auth_code.side_effect = ValueError("code=20276")

    dialog._send_phone_auth_code()

    assert t("qqmusic_phone_frequency") in dialog._phone_status_label.text()
