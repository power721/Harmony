"""
Regression tests for ClickableSlider interactions.
"""

import pytest
from unittest.mock import Mock

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolTip

from ui.widgets.player_controls import ClickableSlider


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_clickable_slider_supports_dragging(qapp):
    """Dragging the slider handle should update value and emit drag signals."""
    slider = ClickableSlider(Qt.Horizontal)
    slider.setRange(0, 1000)
    slider.setValue(500)
    slider.resize(240, 20)
    slider.show()
    qapp.processEvents()

    pressed = []
    released = []
    slider.sliderPressed.connect(lambda: pressed.append(True))
    slider.sliderReleased.connect(lambda: released.append(True))

    start = QPoint(120, 10)
    end = QPoint(220, 10)

    QTest.mousePress(slider, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(slider, end)
    QTest.mouseRelease(slider, Qt.LeftButton, Qt.NoModifier, end)
    qapp.processEvents()

    assert pressed, "sliderPressed should be emitted on drag start"
    assert released, "sliderReleased should be emitted on drag end"
    assert slider.value() > 800, "slider value should follow drag movement"


def test_clickable_slider_enables_mouse_tracking_for_hover_formatter(qapp):
    """Configuring a hover formatter should enable tooltip hover tracking."""
    slider = ClickableSlider(Qt.Horizontal)

    slider.set_hover_tooltip_formatter(lambda value: f"{value}%")

    assert slider.hasMouseTracking() is True


def test_clickable_slider_hover_tooltip_uses_formatter_text(monkeypatch, qapp):
    """Hovering should show tooltip text generated from the hovered slider value."""
    slider = ClickableSlider(Qt.Horizontal)
    slider.setRange(0, 100)
    slider.resize(120, 20)
    slider.show()
    qapp.processEvents()
    slider.set_hover_tooltip_formatter(lambda value: f"{value}%")

    shown = []
    hidden = Mock()
    monkeypatch.setattr(
        QToolTip,
        "showText",
        lambda pos, text, widget: shown.append((pos, text, widget)),
    )
    monkeypatch.setattr(QToolTip, "hideText", hidden)

    event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        slider.rect().center(),
        slider.mapToGlobal(slider.rect().center()),
        Qt.NoButton,
        Qt.NoButton,
        Qt.NoModifier,
    )

    slider._show_hover_tooltip(event)

    assert shown
    assert shown[0][1].endswith("%")
    assert shown[0][2] is slider
    hidden.assert_not_called()
