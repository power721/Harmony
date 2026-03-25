#!/usr/bin/env bash
#
# Automated Qt plugin detection script.
# This script triggers plugin loading without manual interaction.
#
# Usage: ./detect_qt_plugins.sh
#

set -e

OUTPUT_DIR="build_analysis"
LOG_FILE="$OUTPUT_DIR/qt_plugins_auto.log"

mkdir -p "$OUTPUT_DIR"

echo "=============================================="
echo "  Automated Qt Plugin Detection"
echo "=============================================="
echo ""

# Run automated detection
QT_DEBUG_PLUGINS=1 uv run python << 'PYEOF' 2>&1 | tee "$LOG_FILE"
import sys
import os

# Create a test audio file (silent, minimal)
test_file = "/tmp/qt_test_audio.mp3"
if not os.path.exists(test_file):
    # Create a minimal valid MP3 header (silent frame)
    with open(test_file, "wb") as f:
        # Minimal MP3 frame header + silence
        f.write(bytes([
            0xFF, 0xFB, 0x90, 0x00,  # MP3 frame header (128kbps, 44.1kHz, stereo)
        ] + [0x00] * 100))  # Pad with zeros
    print(f"Created test file: {test_file}")

from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl, QTimer

app = QApplication(sys.argv)

print("==> Creating QMediaPlayer and QAudioOutput...")
player = QMediaPlayer()
audio = QAudioOutput()
player.setAudioOutput(audio)

print("==> Setting audio source to trigger plugin loading...")
player.setSource(QUrl.fromLocalFile(test_file))

# Process events to ensure plugins are loaded
app.processEvents()

# Try to start and immediately stop playback
print("==> Attempting brief playback...")
player.play()
app.processEvents()
player.stop()

print("==> Plugin detection complete!")
PYEOF

echo ""
echo "=============================================="
echo "==> Log saved to: $LOG_FILE"
echo ""
echo "==> Detected plugins:"
grep -E "loaded library.*plugins/" "$LOG_FILE" | sed 's/.*plugins\//  /' | sort -u || echo "  (none found)"
echo ""

# Check for critical multimedia plugin
if grep -q "libffmpegmediaplugin" "$LOG_FILE"; then
    echo "✓ Critical: libffmpegmediaplugin.so detected"
else
    echo "✗ WARNING: libffmpegmediaplugin.so NOT detected"
    echo "  This plugin is required for audio playback!"
fi
