#!/usr/bin/env bash
set -e

APP_NAME="Harmony"
APP_VERSION="${APP_VERSION:-1.0.0}"
ENTRY="main.py"
APPDIR="AppDir"
WHITELIST_FILE="build_analysis/qt_plugins_whitelist.txt"
HARMONY_MPV_ONLY="${HARMONY_MPV_ONLY:-1}"

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
        SAFE_DIRS=(platforms imageformats iconengines platforminputcontexts xcbglintegrations wayland)
        if [ "$HARMONY_MPV_ONLY" != "1" ]; then
            SAFE_DIRS+=(multimedia mediaservice audio)
        fi
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

collect_qt_input_context_plugins() {
    echo "==> Ensuring Qt input context plugins are bundled"

    INTERNAL_DIR=$(find dist -type d -path "*_internal" | head -n 1)
    [ -z "$INTERNAL_DIR" ] && { echo "⚠ _internal not found"; return; }

    local bundled_dir="$INTERNAL_DIR/PySide6/Qt/plugins/platforminputcontexts"
    mkdir -p "$bundled_dir"

    local qt_plugins
    qt_plugins=$(uv run python -c 'from PySide6.QtCore import QLibraryInfo; print(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))')
    local source_dir="$qt_plugins/platforminputcontexts"

    if [ ! -d "$source_dir" ]; then
        echo "⚠ Qt input context plugins not found at: $source_dir"
        return
    fi

    cp -a "$source_dir"/. "$bundled_dir"/
    echo "==> Bundled Qt input context plugins from: $source_dir"
    ls -la "$bundled_dir" || true
}

# -------------------------
# 递归收集依赖（避免重复拷贝）
# -------------------------
dep_already_packaged() {
    local base=$1
    local stem
    stem="$(echo "$base" | sed -E 's/\.so(\..*)?$/\.so/')"

    [ -f "$LIB_DIR/$base" ] && return 0
    [ -f "$INTERNAL_DIR/$base" ] && return 0
    [ -f "$INTERNAL_DIR/PySide6/Qt/lib/$base" ] && return 0

    # Consider different SONAME versions as the same family.
    # Example: libicudata.so.73 (Qt bundled) vs libicudata.so.74 (system).
    ls "$LIB_DIR"/"$stem"* >/dev/null 2>&1 && return 0
    ls "$INTERNAL_DIR"/"$stem"* >/dev/null 2>&1 && return 0
    ls "$INTERNAL_DIR"/PySide6/Qt/lib/"$stem"* >/dev/null 2>&1 && return 0

    return 1
}

should_skip_dep() {
    local base=$1

    # Do not bundle core runtime/loader and libc family from build host.
    [[ "$base" =~ ^ld-linux.*\.so ]] && return 0
    [[ "$base" =~ ^lib(c|m|dl|pthread|rt|util|resolv|nsl|anl)\.so(\..*)?$ ]] && return 0
    [[ "$base" =~ ^lib(stdc\+\+|gcc_s)\.so(\..*)?$ ]] && return 0

    # Prefer Qt-bundled copies, avoid mixing host Qt/ICU/codec stacks.
    [[ "$base" =~ ^libQt6.*\.so(\..*)?$ ]] && return 0
    [[ "$base" =~ ^libicu(data|uc|i18n)\.so(\..*)?$ ]] && return 0

    # Avoid pulling an extra host ffmpeg codec stack transitively.
    [[ "$base" =~ ^lib(avcodec|avfilter|avformat|avutil|swresample|swscale|postproc|x26[45]|codec2|placebo|zimg)\.so(\..*)?$ ]] && return 0

    return 1
}

collect_deps_recursive() {
    local file=$1
    local TARGET_DIR=$2

    ldd "$file" | grep "=> /" | awk '{print $3}' | while read -r dep; do
        [ -f "$dep" ] || continue

        base=$(basename "$dep")
        if should_skip_dep "$base"; then
            continue
        fi

        if dep_already_packaged "$base"; then
            continue
        fi

        echo "  + $base"
        cp -L "$dep" "$TARGET_DIR/"
        collect_deps_recursive "$dep" "$TARGET_DIR"
    done
}

# -------------------------
# 收集 Qt + xcb 运行依赖
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

    # 🔥 3. 可选：显式收集 FFmpeg（默认关闭，避免与 Qt/mpv 重复）
    if [ "${HARMONY_BUNDLE_FFMPEG:-0}" = "1" ]; then
        echo "==> Collecting ffmpeg (forced)"
        for lib in libavcodec.so libavformat.so libavutil.so libswresample.so libswscale.so; do
            path=$(ldconfig -p | grep "$lib" | head -n1 | awk '{print $NF}')
            if [ -f "$path" ]; then
                base=$(basename "$path")
                if dep_already_packaged "$base"; then
                    continue
                fi
                echo "  + $lib"
                cp -L "$path" "$LIB_DIR/"
                collect_deps_recursive "$path" "$LIB_DIR"
            else
                echo "  ⚠ Missing $lib"
            fi
        done
    else
        echo "==> Skipping explicit ffmpeg bundling (HARMONY_BUNDLE_FFMPEG=0)"
    fi

    echo "==> Runtime deps done"
}

# -------------------------
# 构建
# -------------------------
build_app() {
    local MODE=$1
    echo "==> Building mode: $MODE"

    rm -rf dist *.spec

    local -a PYI_ARGS=(
      --name "$APP_NAME"
      --noconfirm --windowed --clean --onedir
      --additional-hooks-dir=hooks
      --collect-all certifi
      --hidden-import mpv
      --add-data "plugins/builtin:plugins/builtin"
      --add-data "ui:ui"
      --add-data "translations:translations"
      --add-data "fonts:fonts"
      --add-data "icons:icons"
      --add-data "icon.png:."
    )

    if [ "$HARMONY_MPV_ONLY" = "1" ]; then
        echo "==> mpv-only build: excluding QtMultimedia fallback"
        PYI_ARGS+=(--exclude-module PySide6.QtMultimedia)
        PYI_ARGS+=(--exclude-module PySide6.QtMultimediaWidgets)
        PYI_ARGS+=(--exclude-module infrastructure.audio.qt_backend)
        export HARMONY_ENABLE_QT_FALLBACK=0
    else
        export HARMONY_ENABLE_QT_FALLBACK=1
    fi

    HARMONY_MPV_ONLY="$HARMONY_MPV_ONLY" uv run pyinstaller "${PYI_ARGS[@]}" "$ENTRY"

    collect_qt_input_context_plugins
    prune_qt_plugins "$MODE"
    collect_runtime_deps

    # 保留 Qt 的，删 Python 的
    rm -f dist/Harmony/_internal/lib/libicudata.so.*
    rm -f dist/Harmony/_internal/lib/libicui18n.so.*
    rm -f dist/Harmony/_internal/lib/libicuuc.so.*

    rm -f dist/Harmony/_internal/lib/libgtk-3.so.*
    rm -f dist/Harmony/_internal/libgtk-3.so.*
    rm -f dist/Harmony/_internal/lib/libQt6*.so*
    rm -f dist/Harmony/_internal/lib/libQt6Gui.so.*
    rm -f dist/Harmony/_internal/lib/libQt6Core.so.*

    echo "==> Stripping binaries"
    find dist/"$APP_NAME" -type f \( -name "*.so*" -o -perm /111 \) \
      -exec strip --strip-unneeded {} + 2>/dev/null || true
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
export HARMONY_ENABLE_QT_FALLBACK=0

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
