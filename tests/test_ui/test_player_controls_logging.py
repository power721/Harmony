"""Tests for PlayerControls instance-aware logging."""

from ui.widgets.player_controls import PlayerControls


def test_format_log_message_includes_instance_name():
    controls = PlayerControls.__new__(PlayerControls)
    controls._instance_name = "main"

    message = PlayerControls._format_log_message(controls, "Worker emitting cover_path: /tmp/test.jpg")

    assert message == "[PlayerControls:main] Worker emitting cover_path: /tmp/test.jpg"


def test_format_log_message_uses_default_instance_name():
    controls = PlayerControls.__new__(PlayerControls)
    controls._instance_name = ""

    message = PlayerControls._format_log_message(controls, "Getting cover for online track")

    assert message == "[PlayerControls:default] Getting cover for online track"
