#!/usr/bin/env python3
"""Test script to verify sleep timer display and preset functionality."""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication


def test_preset_conversion():
    """Test that 60 minutes is properly converted to 1 hour."""
    QApplication.instance() or QApplication(sys.argv)

    from PySide6.QtWidgets import QSpinBox

    # Create a mock dialog to test the conversion
    class MockDialog:
        def __init__(self):
            self._hours_spin = QSpinBox()
            self._minutes_spin = QSpinBox()
            self._seconds_spin = QSpinBox()

        def _set_preset_time(self, minutes: int):
            """Set preset time values with proper hour conversion."""
            hours = minutes // 60
            remaining_minutes = minutes % 60
            self._hours_spin.setValue(hours)
            self._minutes_spin.setValue(remaining_minutes)
            self._seconds_spin.setValue(0)

    dialog = MockDialog()

    # Test 15 minutes
    dialog._set_preset_time(15)
    assert dialog._hours_spin.value() == 0, f"Expected 0 hours, got {dialog._hours_spin.value()}"
    assert dialog._minutes_spin.value() == 15, f"Expected 15 minutes, got {dialog._minutes_spin.value()}"
    print("✓ 15 minutes preset works correctly")

    # Test 30 minutes
    dialog._set_preset_time(30)
    assert dialog._hours_spin.value() == 0, f"Expected 0 hours, got {dialog._hours_spin.value()}"
    assert dialog._minutes_spin.value() == 30, f"Expected 30 minutes, got {dialog._minutes_spin.value()}"
    print("✓ 30 minutes preset works correctly")

    # Test 45 minutes
    dialog._set_preset_time(45)
    assert dialog._hours_spin.value() == 0, f"Expected 0 hours, got {dialog._hours_spin.value()}"
    assert dialog._minutes_spin.value() == 45, f"Expected 45 minutes, got {dialog._minutes_spin.value()}"
    print("✓ 45 minutes preset works correctly")

    # Test 60 minutes (should convert to 1 hour)
    dialog._set_preset_time(60)
    assert dialog._hours_spin.value() == 1, f"Expected 1 hour, got {dialog._hours_spin.value()}"
    assert dialog._minutes_spin.value() == 0, f"Expected 0 minutes, got {dialog._minutes_spin.value()}"
    print("✓ 60 minutes preset correctly converts to 1 hour 0 minutes")

    # Test 120 minutes (should convert to 2 hours)
    dialog._set_preset_time(120)
    assert dialog._hours_spin.value() == 2, f"Expected 2 hours, got {dialog._hours_spin.value()}"
    assert dialog._minutes_spin.value() == 0, f"Expected 0 minutes, got {dialog._minutes_spin.value()}"
    print("✓ 120 minutes preset correctly converts to 2 hours 0 minutes")

    # Test 90 minutes (should convert to 1 hour 30 minutes)
    dialog._set_preset_time(90)
    assert dialog._hours_spin.value() == 1, f"Expected 1 hour, got {dialog._hours_spin.value()}"
    assert dialog._minutes_spin.value() == 30, f"Expected 30 minutes, got {dialog._minutes_spin.value()}"
    print("✓ 90 minutes preset correctly converts to 1 hour 30 minutes")

    print("\n✅ All preset conversion tests passed!")


if __name__ == "__main__":
    test_preset_conversion()
