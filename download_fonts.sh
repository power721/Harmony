#!/bin/bash
# Font Download Script for Harmony Music Player
# Downloads OFL-licensed fonts for bundling

set -e

FONTS_DIR="$(dirname "$0")/fonts"

echo "Downloading fonts to: $FONTS_DIR"
echo ""

# Create directories
mkdir -p "$FONTS_DIR/Inter"
mkdir -p "$FONTS_DIR/NotoSansSC"
mkdir -p "$FONTS_DIR/NotoColorEmoji"

# Inter Font (Western UI font)
echo "Downloading Inter font..."
cd "$FONTS_DIR/Inter"
wget -q --show-progress https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip -O Inter.zip || { echo "Failed to download Inter"; exit 1; }
unzip -q Inter.zip
# Inter 4.0 structure: extras/ttf/ contains the font files
if [ -d "Inter-4.0/extras/ttf" ]; then
    cp Inter-4.0/extras/ttf/Inter-Regular.ttf .
    cp Inter-4.0/extras/ttf/Inter-Medium.ttf .
    cp Inter-4.0/extras/ttf/Inter-Bold.ttf .
    rm -rf Inter-4.0 Inter.zip
elif [ -d "extras/ttf" ]; then
    # Already extracted at root level
    cp extras/ttf/Inter-Regular.ttf .
    cp extras/ttf/Inter-Medium.ttf .
    cp extras/ttf/Inter-Bold.ttf .
    rm -rf extras Inter.zip help.txt Inter.ttc InterVariable*.ttf web
else
    echo "Error: Cannot find TTF files in extracted Inter archive"
    ls -la
    exit 1
fi
echo "✓ Inter downloaded"

# Noto Sans SC (Simplified Chinese)
echo "Downloading Noto Sans SC..."
cd "$FONTS_DIR/NotoSansSC"
wget -q --show-progress -O NotoSansSC-Regular.ttf "https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/SC/NotoSansSC-Regular.otf" || { echo "Failed to download Noto Sans SC Regular"; exit 1; }
wget -q --show-progress -O NotoSansSC-Medium.ttf "https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/SC/NotoSansSC-Medium.otf" || { echo "Failed to download Noto Sans SC Medium"; exit 1; }
wget -q --show-progress -O NotoSansSC-Bold.ttf "https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/SC/NotoSansSC-Bold.otf" || { echo "Failed to download Noto Sans SC Bold"; exit 1; }
echo "✓ Noto Sans SC downloaded"

# Noto Color Emoji
echo "Downloading Noto Color Emoji..."
cd "$FONTS_DIR/NotoColorEmoji"
wget -q --show-progress -O NotoColorEmoji.ttf "https://github.com/googlefonts/noto-emoji/raw/main/fonts/NotoColorEmoji.ttf" || { echo "Failed to download Noto Color Emoji"; exit 1; }
echo "✓ Noto Color Emoji downloaded"

echo ""
echo "✓ All fonts downloaded successfully!"
echo ""
echo "Font files:"
ls -lh "$FONTS_DIR/Inter/"*.ttf
ls -lh "$FONTS_DIR/NotoSansSC/"*.ttf
ls -lh "$FONTS_DIR/NotoColorEmoji/"*.ttf
