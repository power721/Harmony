#!/bin/bash
#
# Harmony Music Player - macOS Build Script
# Creates .app bundle and DMG installer
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="Harmony"
APP_VERSION="1.0.0"
DIST_DIR="$SCRIPT_DIR/dist"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"

echo "=========================================="
echo "  $APP_NAME v$APP_VERSION - macOS Build"
echo "=========================================="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required"
    exit 1
fi

# Install PyInstaller if needed
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build dist

# Build executable as directory (for .app bundle)
echo ""
echo "Building executable..."
python3 build.py macos --dir

# Check if build succeeded
if [ ! -d "$APP_BUNDLE" ]; then
    # If PyInstaller didn't create the .app, create it manually
    echo "Creating .app bundle manually..."

    APP_DIR="$DIST_DIR/$APP_NAME.app"
    CONTENTS_DIR="$APP_DIR/Contents"
    MACOS_DIR="$CONTENTS_DIR/MacOS"
    RESOURCES_DIR="$CONTENTS_DIR/Resources"

    mkdir -p "$MACOS_DIR"
    mkdir -p "$RESOURCES_DIR"

    # Copy executable
    if [ -d "$DIST_DIR/$APP_NAME" ]; then
        cp -R "$DIST_DIR/$APP_NAME/"* "$MACOS_DIR/"
    elif [ -f "$DIST_DIR/$APP_NAME" ]; then
        cp "$DIST_DIR/$APP_NAME" "$MACOS_DIR/"
    fi

    # Create Info.plist
    cat > "$CONTENTS_DIR/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>$APP_NAME</string>
    <key>CFBundleExecutable</key>
    <string>$APP_NAME</string>
    <key>CFBundleIconFile</key>
    <string>icon.icns</string>
    <key>CFBundleIdentifier</key>
    <string>com.harmonyplayer.harmony</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>$APP_VERSION</string>
    <key>CFBundleVersion</key>
    <string>$APP_VERSION</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.14</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSMicrophoneUsageDescription</key>
    <string>$APP_NAME needs microphone access for audio visualization</string>
    <key>NSAppleEventsUsageDescription</key>
    <string>$APP_NAME needs to send Apple Events for media key support</string>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>NSSupportsAutomaticGraphicsSwitching</key>
    <true/>
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeName</key>
            <string>Audio File</string>
            <key>CFBundleTypeRole</key>
            <string>Viewer</string>
            <key>LSItemContentTypes</key>
            <array>
                <string>public.mp3</string>
                <string>public.audio</string>
            </array>
        </dict>
    </array>
</dict>
</plist>
EOF

    # Copy icon if available
    if [ -f "$SCRIPT_DIR/icons/icon.icns" ]; then
        cp "$SCRIPT_DIR/icons/icon.icns" "$RESOURCES_DIR/"
    fi

    echo ".app bundle created: $APP_DIR"
fi

# Create DMG
create_dmg() {
    echo ""
    echo "Creating DMG installer..."

    DMG_NAME="${APP_NAME}-${APP_VERSION}.dmg"
    DMG_PATH="$DIST_DIR/$DMG_NAME"

    # Remove existing DMG
    rm -f "$DMG_PATH"

    # Create temporary DMG folder
    DMG_TEMP="$DIST_DIR/dmg_temp"
    mkdir -p "$DMG_TEMP"

    # Copy app bundle
    cp -R "$APP_BUNDLE" "$DMG_TEMP/"

    # Create Applications link
    ln -sf /Applications "$DMG_TEMP/Applications"

    # Create DMG using hdiutil
    hdiutil create -volname "$APP_NAME" -srcfolder "$DMG_TEMP" -ov -format UDZO "$DMG_PATH"

    # Clean up
    rm -rf "$DMG_TEMP"

    echo "DMG created: $DMG_PATH"
}

# Sign the app (requires developer certificate)
sign_app() {
    echo ""
    echo "Signing application..."

    # Check for codesign
    if ! command -v codesign &> /dev/null; then
        echo "codesign not found. Skipping signing."
        return 1
    fi

    # Ask for developer identity
    echo "Available signing identities:"
    security find-identity -v -p codesigning 2>/dev/null | head -5

    read -p "Enter signing identity (or press Enter to skip): " IDENTITY

    if [ -z "$IDENTITY" ]; then
        echo "Skipping signing."
        return 1
    fi

    # Sign the app
    codesign --deep --force --verify --verbose --sign "$IDENTITY" "$APP_BUNDLE"

    # Verify signature
    codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"

    echo "App signed successfully!"
}

# Notarize the app (requires App Store Connect API key)
notarize_app() {
    echo ""
    echo "Notarizing application..."

    if ! command -v notarytool &> /dev/null; then
        echo "notarytool not found. Skipping notarization."
        return 1
    fi

    read -p "Enter Apple ID: " APPLE_ID
    read -p "Enter Team ID: " TEAM_ID
    read -s -p "Enter App-Specific Password: " PASSWORD
    echo ""

    # Submit for notarization
    xcrun notarytool submit "$DMG_PATH" \
        --apple-id "$APPLE_ID" \
        --team-id "$TEAM_ID" \
        --password "$PASSWORD" \
        --wait

    # Staple the ticket
    xcrun stapler staple "$APP_BUNDLE"

    echo "App notarized successfully!"
}

# Main build
echo ""
echo "Build complete!"
echo "App Bundle: $APP_BUNDLE"

# Try to fix libmpv install_name for bundled app (best effort)
if [ -d "$APP_BUNDLE/Contents/MacOS" ]; then
    MPV_LIB=$(find "$APP_BUNDLE/Contents/MacOS" -maxdepth 2 -name "libmpv*.dylib" | head -n 1)
    if [ -n "$MPV_LIB" ] && command -v install_name_tool &> /dev/null; then
        echo "Fixing libmpv install_name: $MPV_LIB"
        install_name_tool -id "@executable_path/$(basename "$MPV_LIB")" "$MPV_LIB" || true
    fi
fi

# Handle command line arguments
case "$1" in
    --dmg)
        create_dmg
        ;;
    --sign)
        sign_app
        ;;
    --notarize)
        create_dmg
        sign_app
        notarize_app
        ;;
    --all)
        create_dmg
        sign_app || true
        ;;
    *)
        echo ""
        echo "To create additional packages:"
        echo "  $0 --dmg        # Create DMG installer"
        echo "  $0 --sign       # Sign the app"
        echo "  $0 --notarize   # Sign, DMG, and notarize"
        echo "  $0 --all        # Create DMG and sign"
        ;;
esac

echo ""
echo "Done!"
