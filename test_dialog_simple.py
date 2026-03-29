"""Simple test to verify sleep timer dialog can open."""

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer
import sys

# Test 1: Basic Qt dialog
app = QApplication(sys.argv)

print("Test 1: Basic QMessageBox")
QMessageBox.information(None, "Test", "Basic Qt dialog works!")

# Test 2: Our sleep timer dialog
print("Test 2: Sleep Timer Dialog")
try:
    from app.bootstrap import Bootstrap
    from ui.dialogs.sleep_timer_dialog import SleepTimerDialog

    bootstrap = Bootstrap.instance()
    service = bootstrap.sleep_timer_service

    print(f"Service: {service}")
    print("Creating dialog...")

    dialog = SleepTimerDialog(service, None)
    print(f"Dialog created: {dialog}")
    print(f"Dialog size: {dialog.size()}")
    print(f"Dialog visible: {dialog.isVisible()}")

    # Show dialog non-modal for testing
    dialog.show()
    print("Dialog shown (non-modal)")

    # Auto-close after 3 seconds
    QTimer.singleShot(3000, app.quit)

    sys.exit(app.exec_())

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
