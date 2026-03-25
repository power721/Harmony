#!/usr/bin/env bash
#
# Collect Qt plugin usage by running the application with debug logging.
# Usage: ./collect_qt_plugins.sh
#
# This script runs the app with QT_DEBUG_PLUGINS=1 to capture which
# plugins are actually loaded during typical usage.
#

set -e

APP="main.py"
OUTPUT_DIR="build_analysis"
LOG_FILE="$OUTPUT_DIR/qt_plugins.log"

mkdir -p "$OUTPUT_DIR"

echo "=============================================="
echo "  Qt Plugin Collection"
echo "=============================================="
echo ""
echo "==> Running application with QT_DEBUG_PLUGINS=1"
echo "==> Log file: $LOG_FILE"
echo ""
echo "IMPORTANT: Interact with the app to load different plugins:"
echo "  - Play some music (THIS IS CRITICAL for multimedia plugins!)"
echo "  - Open settings"
echo "  - Load images/album art"
echo "  - Try different views"
echo ""
echo "Press Ctrl+C when done collecting..."
echo ""

# Run with Qt plugin debug
QT_DEBUG_PLUGINS=1 uv run "$APP" 2>&1 | tee "$LOG_FILE" || true

echo ""
echo "==> Log saved to $LOG_FILE"
echo ""
echo "==> Checking for critical multimedia plugins..."
if grep -q "libffmpegmediaplugin" "$LOG_FILE"; then
    echo "✓ libffmpegmediaplugin.so found in log"
else
    echo "⚠ libffmpegmediaplugin.so NOT found - did you play any music?"
    echo "  Multimedia plugins are loaded lazily during playback!"
fi
