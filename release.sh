#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Harmony"
APP_VERSION="${APP_VERSION:-1.0.0}"
ENTRY="main.py"
APPDIR="AppDir"
TRACE_FILE="build_cache/qt_plugins.txt"

echo "=============================================="
echo "  $APP_NAME $APP_VERSION - FINAL BUILD"
echo "=============================================="

echo "==> Embedding static ffmpeg"

FF_DIR=$(ls -d $FFMPEG_STATIC_DIR 2>/dev/null | head -n1)

if [ -d "$FF_DIR" ]; then
    mkdir -p "$APPDIR/usr/bin/ffmpeg"
    cp "$FF_DIR/ffmpeg" "$APPDIR/usr/bin/ffmpeg/"
    cp "$FF_DIR/ffprobe" "$APPDIR/usr/bin/ffmpeg/"
    chmod +x "$APPDIR/usr/bin/ffmpeg/"*
    echo "  ✓ static ffmpeg embedded"
else
    echo "  ❌ static ffmpeg not found"
    exit 1
fi

mkdir -p build_cache

# -------------------------
# 1. 环境
# -------------------------
uv sync --frozen
rm -rf dist build *.spec "$APPDIR"

# -------------------------
# 2. PyInstaller
# -------------------------
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
  "$ENTRY"

APP_PATH="dist/$APP_NAME"
INTERNAL="$APP_PATH/_internal"
LIB_DIR="$INTERNAL/lib"
PLUGIN_DIR="$INTERNAL/PySide6/Qt/plugins"

mkdir -p "$LIB_DIR"

# -------------------------
# 3. Qt 插件裁剪（缓存版）
# -------------------------
echo "==> Pruning Qt plugins (SAFE MODE)"

if [ ! -d "$PLUGIN_DIR" ]; then
    echo "❌ Plugin dir not found: $PLUGIN_DIR"
    exit 1
fi

# 只删除明确不需要的大模块（安全）
REMOVE_DIRS=(
    "qml"
    "scenegraph"
    "renderers"
    "geometryloaders"
    "position"
    "sensors"
    "webview"
    "webengine"   # ⚠ 很大，但如果你不用 QtWebEngine 可以删
)

for dir in "${REMOVE_DIRS[@]}"; do
    if [ -d "$PLUGIN_DIR/$dir" ]; then
        echo "  - removing $dir"
        rm -rf "$PLUGIN_DIR/$dir"
    fi
done

echo "==> Qt plugin prune done (SAFE MODE)"

# -------------------------
# 4. 依赖收集
# -------------------------
collect_deps() {
    ldd "$1" 2>/dev/null | grep "=> /" | awk '{print $3}' | while read -r dep; do
        [ -f "$dep" ] || continue
        base=$(basename "$dep")
        if [ ! -f "$LIB_DIR/$base" ]; then
            cp -L "$dep" "$LIB_DIR/"
            collect_deps "$dep"
        fi
    done
}

collect_deps "$PLUGIN_DIR/platforms/libqxcb.so"

# xcb 必补
for lib in \
    libxkbcommon.so.0 \
    libxkbcommon-x11.so.0 \
    libxcb-icccm.so.4 \
    libxcb-image.so.0 \
    libxcb-keysyms.so.1 \
    libxcb-render-util.so.0 \
    libxcb-xinerama.so.0 \
    libxcb-xkb.so.1; do

    path=$(ldconfig -p | grep "$lib" | head -n1 | awk '{print $NF}')
    [ -f "$path" ] && cp -L "$path" "$LIB_DIR/"
done

# libstdc++
for lib in libstdc++.so.6 libgcc_s.so.1; do
    path=$(ldconfig -p | grep "$lib" | head -n1 | awk '{print $NF}')
    [ -f "$path" ] && cp -L "$path" "$LIB_DIR/"
done

# ffmpeg
for lib in \
    libavcodec.so.60 \
    libavformat.so.60 \
    libavutil.so.58 \
    libswresample.so.4; do

    path=$(ldconfig -p | grep "$lib" | head -n1 | awk '{print $NF}')
    [ -f "$path" ] && cp -L "$path" "$LIB_DIR/"
done

# -------------------------
# 5. Strip
# -------------------------
find "$APP_PATH" -type f \( -name "*.so*" -o -perm /111 \) \
  -exec strip --strip-unneeded {} + 2>/dev/null || true

# -------------------------
# 6. AppDir
# -------------------------
mkdir -p "$APPDIR/usr/bin"
cp -r "$APP_PATH"/* "$APPDIR/usr/bin/"

mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp icon.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"
cp icon.png "$APPDIR/$APP_NAME.png"

cat > "$APPDIR/$APP_NAME.desktop" << EOF
[Desktop Entry]
Name=$APP_NAME
Exec=$APP_NAME
Icon=$APP_NAME
Type=Application
Categories=AudioVideo;
EOF

# AppRun（优化版）
cat > "$APPDIR/AppRun" << 'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"

export PATH="$HERE/usr/bin/ffmpeg:$HERE/usr/bin:$PATH"
export LD_LIBRARY_PATH="$HERE/usr/bin/_internal/lib:$LD_LIBRARY_PATH"
export QT_PLUGIN_PATH="$HERE/usr/bin/_internal/PySide6/Qt/plugins"

export QT_QPA_PLATFORM=xcb

exec "$HERE/usr/bin/Harmony" "$@"
EOF

chmod +x "$APPDIR/AppRun"

# -------------------------
# 7. AppImage
# -------------------------
APPIMAGETOOL=appimagetool-x86_64.AppImage
[ -f "$APPIMAGETOOL" ] || {
    wget -q https://github.com/AppImage/AppImageKit/releases/download/continuous/$APPIMAGETOOL
    chmod +x "$APPIMAGETOOL"
}

ARCH=x86_64 "./$APPIMAGETOOL" "$APPDIR" "dist/$APP_NAME-$APP_VERSION.AppImage"

echo "✅ FINAL BUILD DONE"
ls -lh dist/