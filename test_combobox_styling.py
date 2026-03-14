#!/usr/bin/env python
"""
Visual test for QComboBox dropdown styling.
This script creates the cover download dialog and displays it for visual inspection.
"""
import sys
from PySide6.QtWidgets import QApplication
from ui.widgets import CoverDownloadDialog
from domain.track import Track
from services.metadata import CoverService
from infrastructure.network import HttpClient


def main():
    # Create QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # Create test data
    http_client = HttpClient()
    cover_service = CoverService(http_client)

    # Create sample tracks
    tracks = [
        Track(
            id=1,
            path="/path/to/song1.mp3",
            title="Test Song 1 - Rock",
            artist="Rock Artist",
            album="Rock Album"
        ),
        Track(
            id=2,
            path="/path/to/song2.mp3",
            title="Test Song 2 - Jazz",
            artist="Jazz Artist",
            album="Jazz Album"
        ),
        Track(
            id=3,
            path="/path/to/song3.mp3",
            title="Test Song 3 - Classical",
            artist="Classical Artist",
            album="Classical Album"
        )
    ]

    # Create and show dialog
    dialog = CoverDownloadDialog(tracks, cover_service)
    dialog.show()

    # Print styling information for verification
    print("=" * 60)
    print("QComboBox Dropdown Styling Test")
    print("=" * 60)
    print("\n✓ Cover Download Dialog created")
    print(f"✓ {len(tracks)} test tracks loaded")
    print("\nStyling Features:")
    print("  • Track selection dropdown (top)")
    print("  • Cover source dropdown (middle)")
    print("\nExpected Results:")
    print("  1. Click on track dropdown → should see white text on dark background")
    print("  2. Click on source dropdown → should see white text on dark background")
    print("  3. Hover over items → should see highlight effect")
    print("  4. Selected items → should show green (#1db954) highlight")
    print("\nDropdown Items:")
    print(f"  • Track combo: {dialog.track_combo.count()} items")
    for i in range(dialog.track_combo.count()):
        print(f"    - {dialog.track_combo.itemText(i)}")

    print(f"  • Source combo: {dialog.source_combo.count()} items")
    for i in range(dialog.source_combo.count()):
        print(f"    - {dialog.source_combo.itemText(i)}")

    # Check if styling is applied
    combo_stylesheet = dialog.track_combo.styleSheet()

    if 'QComboBox QAbstractItemView' in combo_stylesheet:
        print("\n✓ Dropdown list styling is APPLIED")
    else:
        print("\n✗ Dropdown list styling might be missing from styleSheet() method")
        print("  (This is OK if styling is applied via setStyleSheet on dialog)")

    if 'color: #ffffff' in combo_stylesheet or 'color:#ffffff' in combo_stylesheet:
        print("✓ White text color is set")

    if 'selection-background-color: #1db954' in combo_stylesheet:
        print("✓ Green selection highlight is set")

    print("\n" + "=" * 60)
    print("Please test the dropdowns visually in the dialog window")
    print("=" * 60)

    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
