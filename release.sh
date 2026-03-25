#!/usr/bin/env bash
set -e

APP_NAME="Harmony"
APP_VERSION="${APP_VERSION:-1.0.0}"
ENTRY="main.py"
APPDIR="AppDir"
WHITELIST_FILE="build_analysis/qt_plugins_whitelist.txt"

source scripts/qt_env.sh

echo "=============================================="
echo "  $APP_NAME v$APP_VERSION - Release Build"
echo "=============================================="
echo ""

# -------------------------
# Qt plugin whitelist 裁剪
# -------------------------
prune_with_whitelist() {
    echo "==> Pruning with whitelist"

    PLUGIN_DIR=$(find dist -type d -path "*Qt/plugins" | head -n 1)

    [ -d "$PLUGIN_DIR" ] || return

    mapfile -t KEEP_LIST < "$WHITELIST_FILE"

    find "$PLUGIN_DIR" -type f | while read -r file; do
        rel="${file#$PLUGIN_DIR/}"
        keep=false

        for k in "${KEEP_LIST[@]}"; do
            k=$(echo "$k" | tr -d '\r')
            if [[ "$rel" == "$k" ]] || [[ "$rel" == *"$k" ]]; then
                keep=true
                break
            fi
        done

        if [ "$keep" = false ]; then
            rm -f "$file"
        fi
    done

    find "$PLUGIN_DIR" -type d -empty -delete 2>/dev/null || true
}

# -------------------------
# 安全裁剪（绝对不坏音频）
# -------------------------
prune_qt_plugins_safe() {
    echo "==> Safe Qt pruning"

    PLUGIN_DIR=$(find dist -type d -path "*Qt/plugins" | head -n 1)
    [ -d "$PLUGIN_DIR" ] || return

    SAFE_DIRS=(
      platforms
      imageformats
      iconengines
      platforminputcontexts
      multimedia
      mediaservice
      audio
    )

    for dir in "$PLUGIN_DIR"/*; do
        name=$(basename "$dir")
        keep=false

        for k in "${SAFE_DIRS[@]}"; do
            if [[ "$name" == "$k" ]]; then
                keep=true
                break
            fi
        done

        if [ "$keep" = false ]; then
            echo "  Removing dir: $name"
            rm -rf "$dir"
        fi
    done
}

# -------------------------
# aggressive 裁剪
# -------------------------
prune_qt_plugins_aggressive() {
    echo "==> Aggressive Qt pruning"

    if [ -f "$WHITELIST_FILE" ]; then
        prune_with_whitelist
    else
        echo "⚠ No whitelist → fallback safe"
        prune_qt_plugins_safe
    fi
}

# -------------------------
# strip（安全）
# -------------------------
strip_binaries_safe() {
    echo "==> Stripping binaries"

    find dist -type f \
      \( -name "*.so*" -o -perm /111 \) \
      -not -path "*Qt/plugins*" \
      -exec strip --strip-unneeded {} + 2>/dev/null || true
}

# -------------------------
# Runtime 自检（核心）
# -------------------------
check_runtime() {
    echo "==> Runtime self-check"

    APP_BIN=$(find dist -type f -name "$APP_NAME" | head -n 1)

    if [ ! -f "$APP_BIN" ]; then
        echo "❌ Executable not found"
        return 1
    fi

    QT_QPA_PLATFORM=offscreen QT_DEBUG_PLUGINS=1 \
        "$APP_BIN" --version > /dev/null 2> runtime.log || true

    if ! grep -q "libqtmedia_ffmpeg" runtime.log; then
        echo "❌ ffmpeg backend missing"
        tail -n 50 runtime.log
        return 1
    fi

    echo "✅ Runtime OK"
    return 0
}

# -------------------------
# 构建函数（唯一入口）
# -------------------------
build_app() {
    local MODE=$1

    echo ""
    echo "==> Building mode: $MODE"

    rm -rf dist *.spec

    uv run pyinstaller \
      --name "$APP_NAME" \
      --noconfirm \
      --windowed \
      --clean \
      --onedir \
      --additional-hooks-dir=hooks \
      --hidden-import=PySide6.QtCore \
      --hidden-import=PySide6.QtGui \
      --hidden-import=PySide6.QtWidgets \
      --hidden-import=PySide6.QtMultimedia \
      --hidden-import=PySide6.QtMultimediaWidgets \
      --hidden-import=PySide6.QtNetwork \
      --hidden-import=PySide6.QtSvg \
      --collect-all certifi \
      --add-data "ui:ui" \
      --add-data "translations:translations" \
      --add-data "icons:icons" \
      "$ENTRY"

    if [ "$MODE" = "aggressive" ]; then
        prune_qt_plugins_aggressive
    else
        prune_qt_plugins_safe
    fi

    strip_binaries_safe
}

# -------------------------
# Step 1: 安装依赖
# -------------------------
echo "==> [1/6] Sync dependencies"
uv sync --frozen

# -------------------------
# Step 2: 构建（带 fallback）
# -------------------------
echo "==> [2/6] Build with fallback"

build_app aggressive

if check_runtime; then
    echo "✅ Aggressive build succeeded"
else
    echo "⚠ Fallback → safe mode"

    build_app safe

    if check_runtime; then
        echo "✅ Safe build succeeded"
    else
        echo "❌ Safe build FAILED"
        exit 1
    fi
fi

# -------------------------
# Step 3: AppDir
# -------------------------
echo "==> [3/6] Creating AppDir"

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"

cp -r "dist/$APP_NAME"/* "$APPDIR/usr/bin/"

# AppRun
cat > "$APPDIR/AppRun" << 'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"

export PATH="$HERE/usr/bin:$PATH"
export LD_LIBRARY_PATH="$HERE/usr/bin:$HERE/usr/bin/_internal:$LD_LIBRARY_PATH"
export QT_PLUGIN_PATH="$HERE/usr/bin/_internal/PySide6/Qt/plugins"

exec "$HERE/usr/bin/Harmony" "$@"
EOF

chmod +x "$APPDIR/AppRun"

# icon
cp icon.png "$APPDIR/$APP_NAME.png"

# desktop
cat > "$APPDIR/$APP_NAME.desktop" << EOF
[Desktop Entry]
Name=Harmony
Exec=Harmony
Icon=$APP_NAME
Type=Application
Categories=AudioVideo;
EOF

# -------------------------
# Step 4: AppImage
# -------------------------
echo "==> [4/6] Building AppImage"

APPIMAGETOOL=appimagetool-x86_64.AppImage

if [ ! -f "$APPIMAGETOOL" ]; then
    wget -q https://github.com/AppImage/AppImageKit/releases/download/continuous/$APPIMAGETOOL
    chmod +x "$APPIMAGETOOL"
fi

ARCH=x86_64 "./$APPIMAGETOOL" "$APPDIR" "dist/$APP_NAME-$APP_VERSION.AppImage"

# -------------------------
# Done
# -------------------------
echo ""
echo "=============================================="
echo "  Build Complete!"
echo "=============================================="
echo "dist/$APP_NAME-$APP_VERSION.AppImage"