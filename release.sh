#!/usr/bin/env bash
set -e

APP_NAME="Harmony"
APP_VERSION="${APP_VERSION:-1.0.0}"
ENTRY="main.py"
APPDIR="AppDir"
WHITELIST_FILE="build_analysis/qt_plugins_whitelist.txt"

# 确保 uv 环境同步
echo "==> [1/6] Syncing dependencies with uv"
uv sync --frozen

# 加载 Qt 环境变量（如果存在）
[ -f "scripts/qt_env.sh" ] && source scripts/qt_env.sh

echo "=============================================="
echo "  $APP_NAME v$APP_VERSION - Release Build"
echo "=============================================="

# -------------------------
# Qt 插件精简逻辑
# -------------------------
prune_qt_plugins() {
    local MODE=$1
    echo "==> Pruning Qt plugins ($MODE mode)"

    PLUGIN_DIR=$(find dist -type d -path "*PySide6/Qt/plugins" | head -n 1)
    [ -d "$PLUGIN_DIR" ] || { echo "⚠ Plugin dir not found, skipping prune"; return; }

    if [ "$MODE" = "aggressive" ] && [ -f "$WHITELIST_FILE" ]; then
        mapfile -t KEEP_LIST < "$WHITELIST_FILE"
        find "$PLUGIN_DIR" -type f | while read -r file; do
            rel="${file#$PLUGIN_DIR/}"
            keep=false
            for k in "${KEEP_LIST[@]}"; do
                k=$(echo "$k" | tr -d '\r')
                if [[ "$rel" == "$k" ]] || [[ "$rel" == *"$k" ]]; then keep=true; break; fi
            done
            [ "$keep" = false ] && rm -f "$file"
        done
    else
        # Safe Mode: 仅保留核心多媒体和显示组件
        echo "  Using safe-list fallback"
        SAFE_DIRS=(platforms imageformats iconengines platforminputcontexts multimedia mediaservice audio)
        for dir in "$PLUGIN_DIR"/*; do
            name=$(basename "$dir")
            keep=false
            for k in "${SAFE_DIRS[@]}"; do [[ "$name" == "$k" ]] && keep=true && break; done
            [ "$keep" = false ] && rm -rf "$dir"
        done
    fi
    find "$PLUGIN_DIR" -type d -empty -delete 2>/dev/null || true
}

# -------------------------
# 核心构建函数
# -------------------------
build_app() {
    local MODE=$1
    echo "==> Building mode: $MODE"
    rm -rf dist *.spec

    # 使用 uv run 执行 PyInstaller
    uv run pyinstaller \
      --name "$APP_NAME" \
      --noconfirm --windowed --clean --onedir \
      --additional-hooks-dir=hooks \
      --collect-all certifi \
      --hidden-import=PySide6.QtMultimedia \
      --add-data "ui:ui" \
      --add-data "translations:translations" \
      --add-data "icons:icons" \
      "$ENTRY"

    collect_xcb_deps
    prune_qt_plugins "$MODE"

    echo "==> Stripping binaries"
    find dist/"$APP_NAME" -type f \( -name "*.so*" -o -perm /111 \) \
      -exec strip --strip-unneeded {} + 2>/dev/null || true
}

collect_xcb_deps() {
    echo "==> Collecting Qt xcb dependencies"

    TARGET_DIR=$(find dist -type d -path "*_internal" | head -n 1)

    if [ -z "$TARGET_DIR" ]; then
        echo "❌ Cannot find _internal dir"
        return 1
    fi

    mkdir -p "$TARGET_DIR/lib"

    copy_lib() {
        local libname=$1
        local path=$(ldconfig -p | grep "$libname" | head -n1 | awk '{print $NF}')
        if [ -f "$path" ]; then
            echo "  + $libname"
            cp -L "$path" "$TARGET_DIR/lib/"
        else
            echo "  ⚠ Missing $libname"
        fi
    }

    # -------------------------
    # Qt xcb 必备依赖（核心）
    # -------------------------
    copy_lib libxcb.so.1
    copy_lib libxcb-cursor.so.0
    copy_lib libxcb-xinerama.so.0
    copy_lib libxcb-randr.so.0
    copy_lib libxcb-render.so.0
    copy_lib libxcb-shape.so.0
    copy_lib libxcb-xfixes.so.0
    copy_lib libxcb-keysyms.so.1
    copy_lib libxcb-image.so.0
    copy_lib libxcb-icccm.so.4

    copy_lib libxkbcommon.so.0
    copy_lib libxkbcommon-x11.so.0

    copy_lib libX11.so.6
    copy_lib libXext.so.6
    copy_lib libXrender.so.1

    copy_lib libGL.so.1

    echo "==> xcb dependencies collected"
}

# -------------------------
# Runtime 自检
# -------------------------
check_runtime() {
    echo "==> Runtime self-check"

    APP_BIN=$(find dist -type f -name "$APP_NAME" | head -n 1)

    if [ ! -f "$APP_BIN" ]; then
        echo "❌ Executable not found"
        return 1
    fi

    export QT_DEBUG_PLUGINS=1
    export QT_QPA_PLATFORM=minimal   # ✅ 核心修复

    "$APP_BIN" --version > /dev/null 2> runtime.log || true

    # -------------------------
    # 检查 1：Qt 是否正常启动
    # -------------------------
    if grep -q "Could not load the Qt platform plugin" runtime.log; then
        echo "❌ Qt platform plugin failed"
        tail -n 20 runtime.log
        return 1
    fi

    # -------------------------
    # 检查 2：multimedia backend
    # -------------------------
    if ! grep -q "libqtmedia_ffmpeg" runtime.log; then
        echo "❌ ffmpeg backend missing"
        tail -n 20 runtime.log
        return 1
    fi

    echo "✅ Runtime OK"
    return 0
}

# -------------------------
# 主流程
# -------------------------
build_app aggressive
if ! check_runtime; then
    echo "⚠ Aggressive mode failed, falling back to safe mode..."
    build_app safe
    check_runtime || { echo "❌ Critical failure"; exit 1; }
fi

# -------------------------
# AppImage 打包
# -------------------------
echo "==> [3/6] Preparing AppDir"
rm -rf "$APPDIR" && mkdir -p "$APPDIR/usr/bin"
cp -r "dist/$APP_NAME"/* "$APPDIR/usr/bin/"

# 写入 AppRun
cat > "$APPDIR/AppRun" << 'EOF'
#!/usr/bin/env bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}

export PATH="${HERE}/usr/bin:${PATH}"

export LD_LIBRARY_PATH="${HERE}/usr/bin:${HERE}/usr/bin/_internal:${HERE}/usr/bin/_internal/lib:${LD_LIBRARY_PATH}"

export QT_PLUGIN_PATH="${HERE}/usr/bin/_internal/PySide6/Qt/plugins"

# 防止 OpenGL 崩溃
export QT_XCB_GL_INTEGRATION=none

# fallback（无 DISPLAY）
if [ -z "$DISPLAY" ]; then
  export QT_QPA_PLATFORM=minimal
fi

exec "${HERE}/usr/bin/Harmony" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# 图标与桌面文件
cp icons/icon.png "$APPDIR/$APP_NAME.png"
cat > "$APPDIR/$APP_NAME.desktop" << EOF
[Desktop Entry]
Name=Harmony
Exec=Harmony
Icon=$APP_NAME
Type=Application
Categories=AudioVideo;
EOF

echo "==> [4/6] Generating AppImage"
APPIMAGETOOL=appimagetool-x86_64.AppImage
[ -f "$APPIMAGETOOL" ] || { wget -q https://github.com/AppImage/AppImageKit/releases/download/continuous/$APPIMAGETOOL && chmod +x "$APPIMAGETOOL"; }

ARCH=x86_64 "./$APPIMAGETOOL" "$APPDIR" "dist/$APP_NAME-$APP_VERSION-x86_64.AppImage"
echo "✨ Build Complete: dist/$APP_NAME-$APP_VERSION-x86_64.AppImage"