#!/usr/bin/env bash
#
# Harmony Music Player - Release Build Script
#
# Produces optimized AppImage for distribution
#
# Usage: ./release.sh [--no-upx]
#

set -e

APP_NAME="Harmony"
APP_VERSION="${APP_VERSION:-1.0.0}"
ENTRY="main.py"
APPDIR="AppDir"
WHITELIST_FILE="build_analysis/qt_plugins_whitelist.txt"
NO_UPX="${1:-}"

source scripts/qt_env.sh

echo "=============================================="
echo "  $APP_NAME v$APP_VERSION - Release Build"
echo "=============================================="
echo ""

# Step 1: Sync dependencies
echo "==> [1/10] Syncing dependencies (uv)"
uv sync --extra dev --frozen

# Step 2: Clean old build
echo "==> [2/10] Cleaning old build artifacts"
rm -rf build dist *.spec "$APPDIR"

# Step 3: Detect Qt path
echo "==> [3/10] Detecting library paths"
QT_PATH=$(uv run python -c "import PySide6; import os; print(os.path.dirname(PySide6.__file__))")
echo "Qt Path: $QT_PATH"

# Detect OpenSSL
SSL_LIBS=""
SSL_SO=$(uv run python -c "import _ssl; print(_ssl.__file__)" 2>/dev/null || echo "")
if [ -n "$SSL_SO" ] && [ -f "$SSL_SO" ]; then
    while IFS= read -r line; do
        if [[ "$line" == *"libssl.so"* ]] || [[ "$line" == *"libcrypto.so"* ]]; then
            lib_path=$(echo "$line" | sed 's/.*=> //' | sed 's/ (.*//')
            if [ -f "$lib_path" ]; then
                SSL_LIBS="$SSL_LIBS --add-binary $lib_path:."
                echo "  OpenSSL: $lib_path"
            fi
        fi
    done < <(ldd "$SSL_SO" 2>/dev/null)
fi

# Step 4: PyInstaller build
echo "==> [4/10] Building with PyInstaller"

uv run pyinstaller \
  --name "$APP_NAME" \
  --noconfirm \
  --windowed \
  --clean \
  --onedir \
  --additional-hooks-dir=hooks \
  --exclude-module tkinter \
  --exclude-module unittest \
  --exclude-module test \
  --exclude-module pytest \
  --exclude-module matplotlib \
  --exclude-module numpy \
  --exclude-module pandas \
  --exclude-module scipy \
  --exclude-module torch \
  --exclude-module tensorflow \
  --exclude-module IPython \
  --exclude-module jupyter \
  --exclude-module notebook \
  --hidden-import=PySide6.QtCore \
  --hidden-import=PySide6.QtGui \
  --hidden-import=PySide6.QtWidgets \
  --hidden-import=PySide6.QtMultimedia \
  --hidden-import=PySide6.QtMultimediaWidgets \
  --hidden-import=PySide6.QtNetwork \
  --hidden-import=PySide6.QtSvg \
  --hidden-import=ssl \
  --hidden-import=_ssl \
  --collect-all certifi \
  --add-data "ui:ui" \
  --add-data "translations:translations" \
  --add-data "icons:icons" \
  --add-data "icon.png:. " \
  $SSL_LIBS \
  "$ENTRY"

if [ -f "build_analysis/qt_plugins_whitelist.txt" ]; then
  WHITELIST_FILE="build_analysis/qt_plugins_whitelist.txt"
  echo "Using CI-generated whitelist"
else
  echo "⚠ No whitelist found, fallback to safe mode"
  WHITELIST_FILE=""
fi

ls -l build_analysis || true
cat "$WHITELIST_FILE" || true

# Step 5: Qt plugin pruning
echo "==> [5/10] Safe Qt plugin pruning"

PLUGIN_DIR="dist/$APP_NAME/_internal/PySide6/Qt/plugins"

if [ ! -d "$PLUGIN_DIR" ]; then
    PLUGIN_DIR="dist/$APP_NAME/PySide6/Qt/plugins"
fi

if [ ! -d "$PLUGIN_DIR" ]; then
    echo "⚠ Plugin directory not found, skip pruning"
    exit 0
fi

echo "Plugin dir: $PLUGIN_DIR"

# -------------------------
# 安全集合（必须保留）
# -------------------------
SAFE_DIRS=(
  platforms
  imageformats
  iconengines
  platforminputcontexts
  multimedia
  mediaservice
  audio
)

SAFE_FILES=(
  libqxcb.so
  libqtmedia_ffmpeg.so
)

# -------------------------
# 读取 whitelist（安全方式）
# -------------------------
AUTO_LIST=()

if [ -f "$WHITELIST_FILE" ]; then
    echo "Using whitelist: $WHITELIST_FILE"

    # 防止 CRLF / 空行 / set -e 崩溃
    while IFS= read -r line || [ -n "$line" ]; do
        line=$(echo "$line" | tr -d '\r')
        [ -n "$line" ] && AUTO_LIST+=("$line")
    done < "$WHITELIST_FILE"

    echo "Loaded ${#AUTO_LIST[@]} whitelist entries"
else
    echo "⚠ Whitelist not found, fallback to safe mode"
fi

echo "Pruning plugins..."

# -------------------------
# 遍历文件（避免 find 导致 set -e 崩）
# -------------------------
FILES=$(find "$PLUGIN_DIR" -type f 2>/dev/null || true)

for file in $FILES; do
    rel="${file#$PLUGIN_DIR/}"
    keep=false

    # 安全目录
    for d in "${SAFE_DIRS[@]}"; do
        if [[ "$rel" == "$d/"* ]]; then
            keep=true
            break
        fi
    done

    # 关键文件
    if [ "$keep" = false ]; then
        for f in "${SAFE_FILES[@]}"; do
            if [[ "$rel" == *"$f" ]]; then
                keep=true
                break
            fi
        done
    fi

    # 自动 whitelist
    if [ "$keep" = false ] && [ ${#AUTO_LIST[@]} -gt 0 ]; then
        for k in "${AUTO_LIST[@]}"; do
            if [[ "$rel" == "$k" ]] || [[ "$rel" == *"$k" ]]; then
                keep=true
                break
            fi
        done
    fi

    # 删除
    if [ "$keep" = false ]; then
        echo "  Removing: $rel"
        rm -f "$file" || true
    fi
done

# 删除空目录（不能让它失败）
find "$PLUGIN_DIR" -type d -empty -delete 2>/dev/null || true

echo ""
echo "==> Verifying multimedia backend"

PLUGIN_DIR=$(find dist -type d -path "*Qt/plugins" | head -n 1)

if ! find "$PLUGIN_DIR" -name "*ffmpeg*" | grep -q .; then
  echo "❌ ERROR: Qt ffmpeg backend missing!"
  exit 1
fi

echo "✅ ffmpeg backend OK"

# Step 6: Strip binaries
echo "==> [6/10] Stripping binaries"

find "dist/$APP_NAME" -type f \( -name "*.so*" -o -name "*.pyd" -o -perm /111 \) \
    -exec strip --strip-unneeded {} + 2>/dev/null || true

echo "  Done"

# Step 7: UPX compression
echo "==> [7/10] UPX compression"

if [ "$NO_UPX" != "--no-upx" ]; then
    if command -v upx &> /dev/null; then
        # Compress main binaries (not .so files, they may cause issues)
        find "dist/$APP_NAME" -type f -name "*.so*" -size +100k \
            -exec upx --best --lzma {} + 2>/dev/null || true

        # Compress Python shared library
        find "dist/$APP_NAME" -type f -name "libpython*.so*" \
            -exec upx --best --lzma {} + 2>/dev/null || true

        echo "  Done"
    else
        echo "  UPX not found, skipping"
    fi
else
    echo "  Skipping (--no-upx specified)"
fi

echo ""
echo "==> [7.5] Runtime self-check (Qt + Multimedia)"

# 找到输出目录
OUTPUT_DIR="dist/$APP_NAME"

# 兼容不同结构
APP_BIN="$OUTPUT_DIR/$APP_NAME"
if [ ! -f "$APP_BIN" ]; then
    APP_BIN=$(find "$OUTPUT_DIR" -type f -name "$APP_NAME" | head -n 1)
fi

if [ ! -f "$APP_BIN" ]; then
    echo "❌ Executable not found"
    exit 1
fi

echo "Testing: $APP_BIN"

# 使用 CI Qt 环境
source scripts/qt_env.sh

QT_DEBUG_PLUGINS=1 "$APP_BIN" --version > /dev/null 2> runtime.log || true

# -------------------------
# 核心检测：音频 backend
# -------------------------
if ! grep -q "libqtmedia_ffmpeg" runtime.log; then
    echo "❌ ERROR: Qt ffmpeg backend NOT loaded"
    echo "---- runtime.log (tail) ----"
    tail -n 50 runtime.log
    exit 1
fi

echo "✅ Multimedia backend OK"

# Step 8: Create AppDir
echo "==> [8/10] Creating AppDir structure"

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# Copy application
cp -r "dist/$APP_NAME"/* "$APPDIR/usr/bin/"

# Create AppRun
cat > "$APPDIR/AppRun" << 'APPRUN_EOF'
#!/usr/bin/env bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}

export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/bin:${HERE}/usr/bin/_internal:${LD_LIBRARY_PATH}"

# Qt plugin path
export QT_PLUGIN_PATH="${HERE}/usr/bin/_internal/PySide6/Qt/plugins"

exec "${HERE}/usr/bin/Harmony" "$@"
APPRUN_EOF
chmod +x "$APPDIR/AppRun"

# Create desktop file
cat > "$APPDIR/$APP_NAME.desktop" << EOF
[Desktop Entry]
Name=Harmony
Comment=Modern Music Player
Exec=Harmony
Icon=$APP_NAME
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Player;Qt;
Keywords=music;player;audio;
EOF

# Copy icon
cp icon.png "$APPDIR/$APP_NAME.png"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp icon.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"

# Link desktop file
ln -sf "$APP_NAME.desktop" "$APPDIR/usr/share/applications/$APP_NAME.desktop"

# Step 9: Build AppImage
echo "==> [9/10] Building AppImage"

# Download appimagetool if needed
APPIMAGETOOL="appimagetool-x86_64.AppImage"
if [ ! -f "$APPIMAGETOOL" ]; then
    echo "Downloading appimagetool..."
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/$APPIMAGETOOL"
    chmod +x "$APPIMAGETOOL"
fi

# Set architecture
export ARCH=x86_64

# Build AppImage
"./$APPIMAGETOOL" "$APPDIR" "dist/$APP_NAME-$APP_VERSION-x86_64.AppImage"

# Step 10: Report
echo "==> [10/10] Build complete"

SIZE=$(du -sh "dist/$APP_NAME-$APP_VERSION-x86_64.AppImage" | cut -f1)

echo ""
echo "=============================================="
echo "  Release Build Complete!"
echo "=============================================="
echo ""
echo "AppImage: dist/$APP_NAME-$APP_VERSION-x86_64.AppImage"
echo "Size: $SIZE"
echo ""
echo "To run: chmod +x dist/$APP_NAME-$APP_VERSION-x86_64.AppImage && ./dist/$APP_NAME-$APP_VERSION-x86_64.AppImage"
echo ""
