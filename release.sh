#!/usr/bin/env bash
set -e

APP_NAME="Harmony"
APP_VERSION="${APP_VERSION:-1.0.0}"
ENTRY="main.py"
APPDIR="AppDir"
WHITELIST_FILE="build_analysis/qt_plugins_whitelist.txt"

echo "==> [1/6] Syncing dependencies with uv"
uv sync --frozen

[ -f "scripts/qt_env.sh" ] && source scripts/qt_env.sh

echo "=============================================="
echo "  $APP_NAME $APP_VERSION - Release Build"
echo "=============================================="

# -------------------------
# Qt 插件精简
# -------------------------
prune_qt_plugins() {
    local MODE=$1
    echo "==> Pruning Qt plugins ($MODE mode)"

    PLUGIN_DIR=$(find dist -type d -path "*PySide6/Qt/plugins" | head -n 1)
    [ -d "$PLUGIN_DIR" ] || { echo "⚠ Plugin dir not found"; return; }

    if [ "$MODE" = "aggressive" ] && [ -f "$WHITELIST_FILE" ]; then
        mapfile -t KEEP_LIST < "$WHITELIST_FILE"
        find "$PLUGIN_DIR" -type f | while read -r file; do
            rel="${file#$PLUGIN_DIR/}"
            keep=false
            for k in "${KEEP_LIST[@]}"; do
                k=$(echo "$k" | tr -d '\r')
                [[ "$rel" == "$k" || "$rel" == *"$k" ]] && keep=true && break
            done
            [ "$keep" = false ] && rm -f "$file"
        done
    else
        echo "  Using safe-list fallback"
        SAFE_DIRS=(platforms imageformats iconengines platforminputcontexts multimedia mediaservice audio xcbglintegrations wayland)
        for dir in "$PLUGIN_DIR"/*; do
            name=$(basename "$dir")
            keep=false
            for k in "${SAFE_DIRS[@]}"; do
                [[ "$name" == "$k" ]] && keep=true && break
            done
            [ "$keep" = false ] && rm -rf "$dir"
        done
    fi

    find "$PLUGIN_DIR" -type d -empty -delete 2>/dev/null || true
}

# -------------------------
# 递归收集依赖（核心修复）
# -------------------------
collect_deps_recursive() {
    local file=$1
    local TARGET_DIR=$2

    ldd "$file" | grep "=> /" | awk '{print $3}' | while read -r dep; do
        [ -f "$dep" ] || continue

        base=$(basename "$dep")
        if [ ! -f "$TARGET_DIR/$base" ]; then
            echo "  + $base"
            cp -L "$dep" "$TARGET_DIR/"
            collect_deps_recursive "$dep" "$TARGET_DIR"
        fi
    done
}

# -------------------------
# 收集 Qt + xcb + ffmpeg
# -------------------------
collect_runtime_deps() {
    echo "==> Collecting runtime dependencies"

    INTERNAL_DIR=$(find dist -type d -path "*_internal" | head -n 1)
    [ -z "$INTERNAL_DIR" ] && { echo "❌ _internal not found"; exit 1; }

    LIB_DIR="$INTERNAL_DIR/lib"
    mkdir -p "$LIB_DIR"

    PLUGIN_DIR="$INTERNAL_DIR/PySide6/Qt/plugins"

    # 🔥 1. xcb 平台插件依赖
    echo "==> Resolving xcb dependencies"
    collect_deps_recursive "$PLUGIN_DIR/platforms/libqxcb.so" "$LIB_DIR"

    # 🔥 2. OpenGL
    collect_deps_recursive "$(ldconfig -p | grep libGL.so.1 | head -n1 | awk '{print $NF}')" "$LIB_DIR"

    # 🔥 3. Qt Multimedia → ffmpeg
    echo "==> Collecting ffmpeg"

    for lib in libavcodec.so libavformat.so libavutil.so libswresample.so libswscale.so; do
        path=$(ldconfig -p | grep "$lib" | head -n1 | awk '{print $NF}')
        if [ -f "$path" ]; then
            echo "  + $lib"
            cp -L "$path" "$LIB_DIR/"
            collect_deps_recursive "$path" "$LIB_DIR"
        else
            echo "  ⚠ Missing $lib"
        fi
    done

    echo "==> Runtime deps done"
}

# -------------------------
# 构建
# -------------------------
build_app() {
    local MODE=$1
    echo "==> Building mode: $MODE"

    rm -rf dist *.spec

    uv run pyinstaller \
      --name "$APP_NAME" \
      --noconfirm --windowed --clean --onedir \
      --additional-hooks-dir=hooks \
      --collect-all PySide6.QtMultimedia \
      --collect-all certifi \
      --collect-all qqmusic_api \
      --hidden-import=PySide6.QtMultimedia \
      --add-data "ui:ui" \
      --add-data "translations:translations" \
      --add-data "icons:icons" \
      --add-data "icon.png:." \
      "$ENTRY"

    prune_qt_plugins "$MODE"
    collect_runtime_deps

    echo "==> Stripping binaries"
    find dist/"$APP_NAME" -type f \( -name "*.so*" -o -perm /111 \) \
      -exec strip --strip-unneeded {} + 2>/dev/null || true
}

# -------------------------
# Runtime 检测
# -------------------------
check_runtime() {
    echo "==> Runtime self-check"

    APP_BIN=$(find dist -type f -name "$APP_NAME" | head -n 1)
    "$APP_BIN" --version > runtime.log 2>&1 || true

    if grep -q "Could not load the Qt platform plugin" runtime.log; then
        echo "❌ Qt platform plugin error"
        tail -n 20 runtime.log
        return 1
    fi

    if ! grep -qiE "ffmpeg|avcodec|media" runtime.log; then
        echo "❌ ffmpeg backend missing"
        tail -n 20 runtime.log
        return 1
    fi

    echo "✅ Runtime OK"
}

# -------------------------
# 构建执行
# -------------------------
build_app safe

# -------------------------
# AppImage
# -------------------------
echo "==> [3/6] Preparing AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"

cp -r "dist/$APP_NAME"/* "$APPDIR/usr/bin/"

# 🔥 AppRun（已修复）
cat > "$APPDIR/AppRun" << 'EOF'
#!/usr/bin/env bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}

export PATH="${HERE}/usr/bin:${PATH}"

export LD_LIBRARY_PATH="${HERE}/usr/bin:${HERE}/usr/bin/_internal:${HERE}/usr/bin/_internal/lib:${LD_LIBRARY_PATH}"

export QT_PLUGIN_PATH="${HERE}/usr/bin/_internal/PySide6/Qt/plugins"

# OpenGL fallback
export QT_XCB_GL_INTEGRATION=none
export LIBGL_ALWAYS_SOFTWARE=1

# 禁止无头运行
if [ -z "$DISPLAY" ]; then
  echo "❌ No display server found"
  exit 1
fi

exec "${HERE}/usr/bin/Harmony" "$@"
EOF

chmod +x "$APPDIR/AppRun"

cp icon.png "$APPDIR/$APP_NAME.png"

cat > "$APPDIR/$APP_NAME.desktop" << EOF
[Desktop Entry]
Name=Harmony
Exec=Harmony
Icon=$APP_NAME
Type=Application
Categories=AudioVideo;
EOF

echo "==> [4/6] Building AppImage"
APPIMAGETOOL=appimagetool-x86_64.AppImage

[ -f "$APPIMAGETOOL" ] || {
    wget -q https://github.com/AppImage/AppImageKit/releases/download/continuous/$APPIMAGETOOL
    chmod +x "$APPIMAGETOOL"
}

ARCH=x86_64 "./$APPIMAGETOOL" "$APPDIR" "dist/$APP_NAME-$APP_VERSION-x86_64.AppImage"

echo "✨ Build Complete"
ls -lh dist/