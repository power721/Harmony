#!/bin/bash
#
# Harmony Music Player - Linux Build Script
# Creates AppImage, DEB, and RPM packages
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="Harmony"
APP_VERSION="1.0.0"
DIST_DIR="$SCRIPT_DIR/dist"

echo "=========================================="
echo "  $APP_NAME v$APP_VERSION - Linux Build"
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

# Build executable
echo ""
echo "Building executable..."
python3 build.py linux

# Check if build succeeded
if [ ! -f "$DIST_DIR/$APP_NAME" ]; then
    echo "Error: Build failed"
    exit 1
fi

echo ""
echo "Build completed: $DIST_DIR/$APP_NAME"

# Optional: Create AppImage
create_appimage() {
    echo ""
    echo "Creating AppImage..."

    # Check for appimagetool
    if ! command -v appimagetool &> /dev/null; then
        echo "appimagetool not found. Skipping AppImage creation."
        echo "Install with: wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage -O /usr/local/bin/appimagetool && chmod +x /usr/local/bin/appimagetool"
        return 1
    fi

    # Create AppDir structure
    APPDIR="$DIST_DIR/$APP_NAME.AppDir"
    mkdir -p "$APPDIR/usr/bin"
    mkdir -p "$APPDIR/usr/share/applications"
    mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
    mkdir -p "$APPDIR/usr/share/metainfo"

    # Copy executable
    cp "$DIST_DIR/$APP_NAME" "$APPDIR/usr/bin/"

    # Create desktop file
    cat > "$APPDIR/usr/share/applications/$APP_NAME.desktop" << EOF
[Desktop Entry]
Name=$APP_NAME
Comment=Modern Music Player
Exec=$APP_NAME
Icon=$APP_NAME
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Player;Qt;
MimeType=audio/mpeg;audio/flac;audio/ogg;audio/x-vorbis+ogg;audio/mp4;
EOF

    # Create AppStream metadata
    cat > "$APPDIR/usr/share/metainfo/$APP_NAME.metainfo.xml" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>com.harmonyplayer.$APP_NAME</id>
  <name>$APP_NAME</name>
  <summary>Modern Music Player with Spotify-like Interface</summary>
  <metadata_license>MIT</metadata_license>
  <project_license>MIT</project_license>
  <description>
    <p>A modern music player built with PySide6 featuring:</p>
    <ul>
      <li>Spotify-like interface</li>
      <li>Multiple audio format support</li>
      <li>Playlist management</li>
      <li>Lyrics display</li>
      <li>Cloud drive integration</li>
    </ul>
  </description>
  <launchable type="desktop-id">$APP_NAME.desktop</launchable>
  <content_rating type="oars-1.1"/>
</component>
EOF

    # Create AppRun
    cat > "$APPDIR/AppRun" << 'EOF'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${HERE}:${LD_LIBRARY_PATH}"

# Qt plugins path - 输入法支持
export QT_PLUGIN_PATH="${HERE}/usr/bin/PySide6/Qt/plugins:${HERE}/PySide6/Qt/plugins:${QT_PLUGIN_PATH}"
export QT_DEBUG_PLUGINS=0

# GStreamer plugin path
export GST_PLUGIN_PATH="${HERE}/gstreamer-1.0:${HERE}/usr/lib/gstreamer-1.0"
export GST_PLUGIN_SYSTEM_PATH="${HERE}/gstreamer-1.0:${HERE}/usr/lib/gstreamer-1.0"

# Disable GStreamer registry update (use bundled plugins)
export GST_REGISTRY_UPDATE=no

# GLib settings
export GSETTINGS_SCHEMA_DIR="${HERE}/usr/share/glib-2.0/schemas"

exec "${HERE}/usr/bin/Harmony" "$@"
EOF
    chmod +x "$APPDIR/AppRun"

    # Create icon - check multiple locations
    ICON_FOUND=false
    for icon_location in "$SCRIPT_DIR/icon.png" "$SCRIPT_DIR/icons/icon.png" "$SCRIPT_DIR/resources/icon.png"; do
        if [ -f "$icon_location" ]; then
            cp "$icon_location" "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"
            cp "$icon_location" "$APPDIR/$APP_NAME.png"
            ICON_FOUND=true
            echo "Found icon: $icon_location"
            break
        fi
    done

    if [ "$ICON_FOUND" = false ]; then
        echo "Warning: No icon found. AppImage will use default icon."
    fi

    # Link desktop file and icon to AppDir root
    ln -sf "$APPDIR/usr/share/applications/$APP_NAME.desktop" "$APPDIR/$APP_NAME.desktop"
    ln -sf "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png" "$APPDIR/$APP_NAME.png" 2>/dev/null || true

    # Build AppImage with explicit architecture
    ARCH=$(uname -m)
    export ARCH
    appimagetool "$APPDIR" "$DIST_DIR/${APP_NAME}-${APP_VERSION}-${ARCH}.AppImage"

    echo "AppImage created: $DIST_DIR/${APP_NAME}-${APP_VERSION}-${ARCH}.AppImage"
}

# Optional: Create DEB package
create_deb() {
    echo ""
    echo "Creating DEB package..."

    DEB_DIR="$DIST_DIR/deb"
    mkdir -p "$DEB_DIR/DEBIAN"
    mkdir -p "$DEB_DIR/usr/bin"
    mkdir -p "$DEB_DIR/usr/share/applications"
    mkdir -p "$DEB_DIR/usr/share/doc/$APP_NAME"
    mkdir -p "$DEB_DIR/usr/share/man/man1"

    # Copy executable
    cp "$DIST_DIR/$APP_NAME" "$DEB_DIR/usr/bin/"
    chmod 755 "$DEB_DIR/usr/bin/$APP_NAME"

    # Create control file
    cat > "$DEB_DIR/DEBIAN/control" << EOF
Package: harmony
Version: $APP_VERSION
Section: sound
Priority: optional
Architecture: amd64
Depends: libc6 (>= 2.17), libgl1, libpulse0, libxcb1, libxkbcommon0
Maintainer: Harmony Player <support@harmonyplayer.com>
Description: Modern Music Player
 A PySide6-based music player with a modern, Spotify-like interface.
 Supports multiple audio formats including MP3, FLAC, OGG, M4A, and WAV.
 Features include playlist management, lyrics display, album art,
 and cloud drive integration.
EOF

    # Create desktop file
    cat > "$DEB_DIR/usr/share/applications/$APP_NAME.desktop" << EOF
[Desktop Entry]
Name=$APP_NAME
Comment=Modern Music Player
Exec=/usr/bin/$APP_NAME
Icon=$APP_NAME
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Player;Qt;
MimeType=audio/mpeg;audio/flac;audio/ogg;audio/x-vorbis+ogg;audio/mp4;
EOF

    # Build DEB
    DEB_PACKAGE="$DIST_DIR/${APP_NAME}_${APP_VERSION}_amd64.deb"
    dpkg-deb --build "$DEB_DIR" "$DEB_PACKAGE"

    echo "DEB package created: $DEB_PACKAGE"
}

# Check for command line arguments
if [ "$1" = "--appimage" ]; then
    create_appimage
elif [ "$1" = "--deb" ]; then
    create_deb
elif [ "$1" = "--all" ]; then
    create_appimage || true
    create_deb || true
fi

echo ""
echo "Build complete!"
echo "Executable: $DIST_DIR/$APP_NAME"
echo ""
echo "To create additional packages:"
echo "  $0 --appimage   # Create AppImage"
echo "  $0 --deb        # Create DEB package"
echo "  $0 --all        # Create all packages"
