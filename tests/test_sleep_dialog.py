#!/usr/bin/env python3
"""Test sleep timer dialog."""

import sys
from PySide6.QtWidgets import QApplication
from app.bootstrap import Bootstrap
from ui.dialogs.sleep_timer_dialog import SleepTimerDialog

def main():
    app = QApplication(sys.argv)

    # Initialize bootstrap
    bootstrap = Bootstrap.instance()

    # Get sleep timer service
    sleep_timer_service = bootstrap.sleep_timer_service

    # Create and show dialog
    dialog = SleepTimerDialog(sleep_timer_service)
    dialog.show()

    print("Dialog created and shown successfully!")
    print(f"Dialog title: {dialog.windowTitle()}")
    print(f"Dialog size: {dialog.size()}")
    print(f"Dialog modal: {dialog.isModal()}")

    # Don't exec, just show briefly
    QTimer.singleShot(1000, app.quit)
    sys.exit(app.exec_())

if __name__ == "__main__":
    from PySide6.QtCore import QTimer
    main()
