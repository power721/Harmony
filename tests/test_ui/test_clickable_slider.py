"""
Regression tests for ClickableSlider interactions.
"""

import pytest

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

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
