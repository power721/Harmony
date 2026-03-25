#!/bin/bash
#
# Harmony Music Player - Linux Build Script
# Creates AppImage, DEB, and RPM packages
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="Harmony"
APP_VERSION="${APP_VERSION:-1.0.0}"
DIST_DIR="$SCRIPT_DIR/dist"
APPDIR="AppDir"

echo "=========================================="
echo "  $APP_NAME v$APP_VERSION - Linux Build"
echo "=========================================="

# Build using release.sh first
build_base() {
    echo ""
    echo "==> Building base application..."

    if [ ! -d "$DIST_DIR/$APP_NAME" ]; then
        chmod +x release.sh
        ./release.sh
    fi

    if [ ! -d "$DIST_DIR/$APP_NAME" ]; then
        echo "Error: Build failed"
        exit 1
    fi

    echo "Base build completed: $DIST_DIR/$APP_NAME"
}

# Create AppImage
create_appimage() {
    echo ""
    echo "==> Creating AppImage..."

    # Check for appimagetool
    APPIMAGETOOL="appimagetool-x86_64.AppImage"
    if ! command -v appimagetool &> /dev/null; then
        if [ ! -f "$APPIMAGETOOL" ]; then
            echo "Downloading appimagetool..."
            wget -q https://github.com/AppImage/AppImageKit/releases/download/continuous/$APPIMAGETOOL
            chmod +x "$APPIMAGETOOL"
        fi
        APPIMAGETOOL="./$APPIMAGETOOL"
    else
        APPIMAGETOOL="appimagetool"
    fi

    # Create AppDir structure
    rm -rf "$APPDIR"
    mkdir -p "$APPDIR/usr/bin"
    mkdir -p "$APPDIR/usr/share/applications"
    mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
    mkdir -p "$APPDIR/usr/share/metainfo"

    # Copy application
    cp -r "$DIST_DIR/$APP_NAME"/* "$APPDIR/usr/bin/"

    # Create desktop file
    cat > "$APPDIR/usr/share/applications/$APP_NAME.desktop" << EOF
[Desktop Entry]
Name=$APP_NAME
Comment=Modern Music Player
Exec=Harmony
Icon=$APP_NAME
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Player;Qt;
MimeType=audio/mpeg;audio/flac;audio/ogg;audio/x-vorbis+ogg;audio/mp4;
StartupWMClass=$APP_NAME
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
export LD_LIBRARY_PATH="${HERE}/usr/bin:${HERE}/usr/bin/_internal:${HERE}/usr/bin/_internal/lib:${LD_LIBRARY_PATH}"

# Qt plugins path - 输入法支持
export QT_PLUGIN_PATH="${HERE}/usr/bin/_internal/PySide6/Qt/plugins"
export QT_DEBUG_PLUGINS=0

# OpenGL fallback
export QT_XCB_GL_INTEGRATION=none
export LIBGL_ALWAYS_SOFTWARE=1

if [ -z "$DISPLAY" ]; then
  echo "Error: No display server found"
  exit 1
fi

exec "${HERE}/usr/bin/Harmony" "$@"
EOF
    chmod +x "$APPDIR/AppRun"

    # Copy icon
    if [ -f "$SCRIPT_DIR/icon.png" ]; then
        cp "$SCRIPT_DIR/icon.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"
        cp "$SCRIPT_DIR/icon.png" "$APPDIR/$APP_NAME.png"
    fi

    # Link files to AppDir root
    ln -sf "$APPDIR/usr/share/applications/$APP_NAME.desktop" "$APPDIR/$APP_NAME.desktop"

    # Build AppImage
    ARCH=$(uname -m)
    export ARCH
    $APPIMAGETOOL "$APPDIR" "$DIST_DIR/${APP_NAME}-${APP_VERSION}-${ARCH}.AppImage"

    echo "AppImage created: $DIST_DIR/${APP_NAME}-${APP_VERSION}-${ARCH}.AppImage"
}

# Create DEB package
create_deb() {
    echo ""
    echo "==> Creating DEB package..."

    DEB_DIR="$DIST_DIR/deb"
    rm -rf "$DEB_DIR"
    mkdir -p "$DEB_DIR/DEBIAN"
    mkdir -p "$DEB_DIR/usr/lib/$APP_NAME"
    mkdir -p "$DEB_DIR/usr/bin"
    mkdir -p "$DEB_DIR/usr/share/applications"
    mkdir -p "$DEB_DIR/usr/share/icons/hicolor/256x256/apps"
    mkdir -p "$DEB_DIR/usr/share/doc/$APP_NAME"
    mkdir -p "$DEB_DIR/usr/share/metainfo"

    # Copy application
    cp -r "$DIST_DIR/$APP_NAME"/* "$DEB_DIR/usr/lib/$APP_NAME/"

    # Create wrapper script
    cat > "$DEB_DIR/usr/bin/$APP_NAME" << EOF
#!/bin/bash
export QT_PLUGIN_PATH="/usr/lib/$APP_NAME/_internal/PySide6/Qt/plugins"
export LD_LIBRARY_PATH="/usr/lib/$APP_NAME/_internal/lib:\$LD_LIBRARY_PATH"
exec /usr/lib/$APP_NAME/$APP_NAME "\$@"
EOF
    chmod 755 "$DEB_DIR/usr/bin/$APP_NAME"

    # Create control file
    cat > "$DEB_DIR/DEBIAN/control" << EOF
Package: harmony
Version: $APP_VERSION
Section: sound
Priority: optional
Architecture: amd64
Depends: libc6 (>= 2.17), libgl1, libpulse0, libxcb1, libxkbcommon0, libglib2.0-0
Maintainer: Harmony Player <support@harmonyplayer.com>
Description: Modern Music Player
 A PySide6-based music player with a modern, Spotify-like interface.
 Supports multiple audio formats including MP3, FLAC, OGG, M4A, and WAV.
 Features include playlist management, lyrics display, album art,
 and cloud drive integration.
EOF

    # Create postinst script
    cat > "$DEB_DIR/DEBIAN/postinst" << 'EOF'
#!/bin/bash
set -e
update-desktop-database /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true
EOF
    chmod 755 "$DEB_DIR/DEBIAN/postinst"

    # Create prerm script
    cat > "$DEB_DIR/DEBIAN/prerm" << 'EOF'
#!/bin/bash
set -e
EOF
    chmod 755 "$DEB_DIR/DEBIAN/prerm"

    # Create desktop file
    cat > "$DEB_DIR/usr/share/applications/$APP_NAME.desktop" << EOF
[Desktop Entry]
Name=$APP_NAME
Comment=Modern Music Player
Exec=$APP_NAME
Icon=$APP_NAME
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Player;Qt;
MimeType=audio/mpeg;audio/flac;audio/ogg;audio/x-vorbis+ogg;audio/mp4;
StartupWMClass=$APP_NAME
EOF

    # Copy icon
    if [ -f "$SCRIPT_DIR/icon.png" ]; then
        cp "$SCRIPT_DIR/icon.png" "$DEB_DIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"
    fi

    # Copy metainfo
    if [ -f "$APPDIR/usr/share/metainfo/$APP_NAME.metainfo.xml" ]; then
        cp "$APPDIR/usr/share/metainfo/$APP_NAME.metainfo.xml" "$DEB_DIR/usr/share/metainfo/"
    fi

    # Build DEB
    DEB_PACKAGE="$DIST_DIR/${APP_NAME}_${APP_VERSION}_amd64.deb"
    dpkg-deb --build "$DEB_DIR" "$DEB_PACKAGE"

    echo "DEB package created: $DEB_PACKAGE"
}

# Create RPM package
create_rpm() {
    echo ""
    echo "==> Creating RPM package..."

    # Check for rpmbuild
    if ! command -v rpmbuild &> /dev/null; then
        echo "Error: rpmbuild not found. Install with: sudo apt install rpm"
        return 1
    fi

    RPM_DIR="$DIST_DIR/rpm"
    rm -rf "$RPM_DIR"
    mkdir -p "$RPM_DIR/SOURCES"
    mkdir -p "$RPM_DIR/SPECS"
    mkdir -p "$RPM_DIR/BUILD"
    mkdir -p "$RPM_DIR/RPMS"

    # Create tarball for RPM
    TARBALL="$RPM_DIR/SOURCES/$APP_NAME-$APP_VERSION.tar.gz"
    mkdir -p "$DIST_DIR/$APP_NAME-$APP_VERSION"
    cp -r "$DIST_DIR/$APP_NAME"/* "$DIST_DIR/$APP_NAME-$APP_VERSION/"
    tar -czf "$TARBALL" -C "$DIST_DIR" "$APP_NAME-$APP_VERSION"
    rm -rf "$DIST_DIR/$APP_NAME-$APP_VERSION"

    # Create RPM spec file
    cat > "$RPM_DIR/SPECS/$APP_NAME.spec" << EOF
Name:           $APP_NAME
Version:        $APP_VERSION
Release:        1%{?dist}
Summary:        Modern Music Player with Spotify-like Interface

License:        MIT
URL:            https://github.com/harmonyplayer/harmony
Source0:        %{name}-%{version}.tar.gz

BuildArch:      x86_64
Requires:       glibc >= 2.17, libglvnd, pulseaudio-libs, libxcb, libxkbcommon
Requires:       glib2, qt6-qtbase

%description
A PySide6-based music player with a modern, Spotify-like interface.
Supports multiple audio formats including MP3, FLAC, OGG, M4A, and WAV.
Features include playlist management, lyrics display, album art,
and cloud drive integration.

%prep
%setup -q

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/usr/lib/%{name}
cp -r * %{buildroot}/usr/lib/%{name}/

mkdir -p %{buildroot}/usr/bin
cat > %{buildroot}/usr/bin/%{name} << 'WRAPPER'
#!/bin/bash
export QT_PLUGIN_PATH="/usr/lib/$APP_NAME/_internal/PySide6/Qt/plugins"
export LD_LIBRARY_PATH="/usr/lib/$APP_NAME/_internal/lib:\$LD_LIBRARY_PATH"
exec /usr/lib/$APP_NAME/$APP_NAME "\$@"
WRAPPER
chmod 755 %{buildroot}/usr/bin/%{name}

mkdir -p %{buildroot}/usr/share/applications
cat > %{buildroot}/usr/share/applications/%{name}.desktop << 'DESKTOP'
[Desktop Entry]
Name=$APP_NAME
Comment=Modern Music Player
Exec=$APP_NAME
Icon=$APP_NAME
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Player;Qt;
MimeType=audio/mpeg;audio/flac;audio/ogg;audio/x-vorbis+ogg;audio/mp4;
StartupWMClass=$APP_NAME
DESKTOP

mkdir -p %{buildroot}/usr/share/icons/hicolor/256x256/apps
%if 0%{?fedora} || 0%{?rhel} >= 8
# Icon will be added separately
%endif

%files
%defattr(-,root,root,-)
/usr/lib/%{name}
/usr/bin/%{name}
/usr/share/applications/%{name}.desktop
%attr(644,root,root) /usr/share/icons/hicolor/256x256/apps/%{name}.png

%post
update-desktop-database /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true

%postun
update-desktop-database /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true

%changelog
* $(date '+%a %b %d %Y') Harmony Player <support@harmonyplayer.com> - $APP_VERSION-1
- Initial package
EOF

    # Build RPM
    rpmbuild --define "_topdir $RPM_DIR" -bb "$RPM_DIR/SPECS/$APP_NAME.spec"

    # Copy RPM to dist
    find "$RPM_DIR/RPMS" -name "*.rpm" -exec cp {} "$DIST_DIR/" \;

    echo "RPM package created: $DIST_DIR/$APP_NAME-$APP_VERSION-1.x86_64.rpm"
}

# Main
case "${1:-}" in
    --appimage)
        build_base
        create_appimage
        ;;
    --deb)
        build_base
        create_appimage  # Need AppDir for metainfo
        create_deb
        ;;
    --rpm)
        build_base
        create_rpm
        ;;
    --all)
        build_base
        create_appimage
        create_deb
        create_rpm || echo "RPM build skipped (rpmbuild not available)"
        ;;
    "")
        build_base
        create_appimage
        ;;
    *)
        echo "Usage: $0 [--appimage|--deb|--rpm|--all]"
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "Build complete!"
echo "=========================================="
ls -lh "$DIST_DIR"/*.{AppImage,deb,rpm} 2>/dev/null || true
