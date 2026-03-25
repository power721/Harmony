#!/usr/bin/env bash
set -uo pipefail

APP_NAME="Harmony"
APP_VERSION="${APP_VERSION:-1.0.0}"
ENTRY="main.py"
APPDIR="AppDir"

echo "=============================================="
echo "  $APP_NAME $APP_VERSION - STABLE BUILD"
echo "=============================================="

# -------------------------
# 0. 环境
# -------------------------
echo "==> Preparing environment"
uv sync --frozen

rm -rf dist build *.spec "$APPDIR"

# -------------------------
# 1. PyInstaller（关键步骤）
# -------------------------
echo "==> Building with PyInstaller"

uv run pyinstaller \
  --name "$APP_NAME" \
  --noconfirm --windowed --clean --onedir \
  --collect-all PySide6 \
  --collect-all PySide6.QtMultimedia \
  --collect-all certifi \
  --hidden-import=PySide6.QtMultimedia \
  --add-data "ui:ui" \
  --add-data "translations:translations" \
  --add-data "icons:icons" \
  --add-data "icon.png:." \
  "$ENTRY" || {
    echo "❌ PyInstaller failed"
    exit 1
}

APP_PATH="dist/$APP_NAME"
INTERNAL="$APP_PATH/_internal"
PLUGIN_DIR="$INTERNAL/PySide6/Qt/plugins"

# -------------------------
# 2. Qt 插件裁剪（SAFE MODE）
# -------------------------
echo "==> Pruning Qt plugins (SAFE MODE)"

if [ -d "$PLUGIN_DIR" ]; then
    REMOVE_DIRS=(
        "qml"
        "renderers"
        "geometryloaders"
        "position"
        "sensors"
        "webview"
        "webengine"
    )

    for dir in "${REMOVE_DIRS[@]}"; do
        if [ -d "$PLUGIN_DIR/$dir" ]; then
            echo "  - removing $dir"
            rm -rf "$PLUGIN_DIR/$dir"
        fi
    done

    echo "==> Qt plugin prune done"
else
    echo "⚠ Plugin dir not found, skipping prune"
fi

# -------------------------
# 3. Strip（二进制瘦身，可失败）
# -------------------------
echo "==> Stripping binaries (optional)"

find "$APP_PATH" -type f \( -name "*.so*" -o -perm /111 \) \
  -exec strip --strip-unneeded {} + 2>/dev/null || true

# -------------------------
# 4. AppDir 结构
# -------------------------
echo "==> Preparing AppDir"

mkdir -p "$APPDIR/usr/bin"

cp -r "$APP_PATH"/* "$APPDIR/usr/bin/" || {
    echo "❌ Copy to AppDir failed"
    exit 1
}

# -------------------------
# 5. 静态 ffmpeg（可选但推荐）
# -------------------------
echo "==> Embedding static ffmpeg"

if compgen -G "ffmpeg-*-amd64-static" > /dev/null; then
    FF_DIR=$(ls -d ffmpeg-*-amd64-static | head -n1)

    mkdir -p "$APPDIR/usr/bin/ffmpeg"

    if [ -f "$FF_DIR/ffmpeg" ]; then
        cp "$FF_DIR/ffmpeg" "$APPDIR/usr/bin/ffmpeg/"
        chmod +x "$APPDIR/usr/bin/ffmpeg/ffmpeg"
    fi

    if [ -f "$FF_DIR/ffprobe" ]; then
        cp "$FF_DIR/ffprobe" "$APPDIR/usr/bin/ffmpeg/"
        chmod +x "$APPDIR/usr/bin/ffmpeg/ffprobe"
    fi

    echo "  ✓ ffmpeg embedded"
else
    echo "⚠ No static ffmpeg found, skipping"
fi

# -------------------------
# 6. Desktop & Icon
# -------------------------
echo "==> Creating desktop entry"

mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp icon.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png" 2>/dev/null || true
cp icon.png "$APPDIR/$APP_NAME.png" 2>/dev/null || true

cat > "$APPDIR/$APP_NAME.desktop" << EOF
[Desktop Entry]
Name=$APP_NAME
Exec=$APP_NAME
Icon=$APP_NAME
Type=Application
Categories=AudioVideo;
EOF

# -------------------------
# 7. AppRun
# -------------------------
echo "==> Creating AppRun"

cat > "$APPDIR/AppRun" << 'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"

export PATH="$HERE/usr/bin/ffmpeg:$HERE/usr/bin:$PATH"
export LD_LIBRARY_PATH="$HERE/usr/bin/_internal:$HERE/usr/bin/_internal/lib:$LD_LIBRARY_PATH"
export QT_PLUGIN_PATH="$HERE/usr/bin/_internal/PySide6/Qt/plugins"

export QT_QPA_PLATFORM=xcb

exec "$HERE/usr/bin/Harmony" "$@"
EOF

chmod +x "$APPDIR/AppRun"

# -------------------------
# 8. AppImage（关键步骤）
# -------------------------
echo "==> Building AppImage"

APPIMAGETOOL=appimagetool-x86_64.AppImage

if [ ! -f "$APPIMAGETOOL" ]; then
    wget -q https://github.com/AppImage/AppImageKit/releases/download/continuous/$APPIMAGETOOL
    chmod +x "$APPIMAGETOOL"
fi

ARCH=x86_64 "./$APPIMAGETOOL" "$APPDIR" "dist/$APP_NAME-$APP_VERSION.AppImage" || {
    echo "❌ AppImage build failed"
    exit 1
}

# -------------------------
# 9. 输出
# -------------------------
echo "=============================================="
echo "✅ BUILD SUCCESS"
echo "=============================================="

ls -lh dist/ || true