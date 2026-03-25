#!/usr/bin/env bash
#
# Harmony Music Player - Production Build Script
#
# Features:
#   - uv for dependency management
#   - PyInstaller for packaging
#   - Automatic Qt plugin pruning (whitelist-based)
#   - SSL library bundling
#   - Binary stripping for size optimization
#
# Usage:
#   ./build_uv.sh [--onedir|--onefile] [--no-strip]
#

set -e

APP_NAME="Harmony"
ENTRY="main.py"
MODE="${1:---onedir}"
NO_STRIP="${2:-}"
WHITELIST_FILE="build_analysis/qt_plugins_whitelist.txt"

echo "=============================================="
echo "  $APP_NAME - Production Build"
echo "=============================================="

# Step 1: Sync dependencies with uv
echo ""
echo "==> [1/8] Syncing dependencies (uv)"
uv sync --extra dev

# Step 2: Activate venv
echo ""
echo "==> [2/8] Activating virtual environment"
source .venv/bin/activate

# Step 3: Clean old build
echo ""
echo "==> [3/8] Cleaning old build artifacts"
rm -rf build dist *.spec

# Step 4: Detect paths
echo ""
echo "==> [4/8] Detecting library paths"
QT_PATH=$(python -c "import PySide6; import os; print(os.path.dirname(PySide6.__file__))")
echo "Qt Path: $QT_PATH"

# Detect OpenSSL libraries
echo ""
echo "Detecting OpenSSL libraries..."
SSL_LIBS=""

# Method 1: Via _ssl module
SSL_SO=$(python -c "import _ssl; print(_ssl.__file__)" 2>/dev/null || echo "")
if [ -n "$SSL_SO" ] && [ -f "$SSL_SO" ]; then
    echo "Found _ssl module: $SSL_SO"
    # Get linked libraries
    if command -v ldd &> /dev/null; then
        while IFS= read -r line; do
            if [[ "$line" == *"libssl.so"* ]] || [[ "$line" == *"libcrypto.so"* ]]; then
                lib_path=$(echo "$line" | sed 's/.*=> //' | sed 's/ (.*//')
                if [ -f "$lib_path" ]; then
                    SSL_LIBS="$SSL_LIBS --add-binary $lib_path:."
                    echo "  OpenSSL lib: $lib_path"
                fi
            fi
        done < <(ldd "$SSL_SO" 2>/dev/null)
    fi
fi

# Method 2: Check conda environment
CONDA_PREFIX="${CONDA_PREFIX:-}"
if [ -n "$CONDA_PREFIX" ]; then
    echo "Conda environment: $CONDA_PREFIX"
    for lib in libssl.so.3 libcrypto.so.3 libssl.so.1.1 libcrypto.so.1.1; do
        lib_path="$CONDA_PREFIX/lib/$lib"
        if [ -f "$lib_path" ]; then
            SSL_LIBS="$SSL_LIBS --add-binary $lib_path:."
            echo "  Conda SSL lib: $lib_path"
        fi
    done
fi

# Method 3: System libraries
if [ -z "$SSL_LIBS" ]; then
    echo "No SSL libs found via Python/Conda, checking system..."
    for lib_path in /usr/lib/x86_64-linux-gnu/libssl.so.3 \
                    /usr/lib/x86_64-linux-gnu/libcrypto.so.3 \
                    /usr/lib/x86_64-linux-gnu/libssl.so.1.1 \
                    /usr/lib/x86_64-linux-gnu/libcrypto.so.1.1; do
        if [ -f "$lib_path" ]; then
            SSL_LIBS="$SSL_LIBS --add-binary $lib_path:."
            echo "  System SSL lib: $lib_path"
        fi
    done
fi

if [ -z "$SSL_LIBS" ]; then
    echo "WARNING: No OpenSSL libraries found! HTTPS may not work."
fi

# Step 5: Build with PyInstaller
echo ""
echo "==> [5/8] Building with PyInstaller ($MODE)"

pyinstaller \
  --name "$APP_NAME" \
  --noconfirm \
  --windowed \
  --clean \
  $MODE \
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

# Step 6: Qt plugin pruning (whitelist-based)
echo ""
echo "==> [6/8] Pruning Qt plugins"

if [ "$MODE" == "--onedir" ]; then
    PLUGIN_DIR="dist/$APP_NAME/_internal/PySide6/Qt/plugins"

    # Fallback to alternate location
    if [ ! -d "$PLUGIN_DIR" ]; then
        PLUGIN_DIR="dist/$APP_NAME/PySide6/Qt/plugins"
    fi

    if [ -d "$PLUGIN_DIR" ]; then
        if [ -f "$WHITELIST_FILE" ]; then
            echo "Using whitelist: $WHITELIST_FILE"

            # Read whitelist into array
            mapfile -t KEEP_LIST < "$WHITELIST_FILE"

            # Process each plugin file
            while IFS= read -r -d '' file; do
                rel="${file#$PLUGIN_DIR/}"
                keep=false

                for k in "${KEEP_LIST[@]}"; do
                    # Normalize comparison
                    k_norm=$(echo "$k" | tr -d '\r')
                    if [[ "$rel" == "$k_norm" ]] || [[ "$rel" == *"$k_norm" ]]; then
                        keep=true
                        break
                    fi
                done

                if [ "$keep" = false ]; then
                    echo "  Removing: $rel"
                    rm -f "$file"
                fi
            done < <(find "$PLUGIN_DIR" -type f -print0 2>/dev/null)

            # Remove empty directories
            find "$PLUGIN_DIR" -type d -empty -delete 2>/dev/null

        else
            echo "Whitelist not found, using fallback pruning..."

            # Fallback: keep essential plugins for music player
            KEEP_PLUGINS=(
                "platforms"
                "imageformats"
                "iconengines"
                "multimedia"
                "audio"
                "mediaservice"
                "platforminputcontexts"
            )

            for dir in "$PLUGIN_DIR"/*; do
                if [ -d "$dir" ]; then
                    name=$(basename "$dir")
                    keep=false

                    for k in "${KEEP_PLUGINS[@]}"; do
                        if [[ "$name" == "$k" ]]; then
                            keep=true
                            break
                        fi
                    done

                    if [ "$keep" = false ]; then
                        echo "  Removing plugin dir: $name"
                        rm -rf "$dir"
                    fi
                fi
            done
        fi
    else
        echo "Plugin directory not found: $PLUGIN_DIR"
    fi
else
    echo "  Skipping plugin pruning for onefile mode"
fi

# Step 7: Strip binaries (reduce size)
echo ""
echo "==> [7/8] Stripping binaries"

if [ "$NO_STRIP" != "--no-strip" ]; then
    if [ "$MODE" == "--onedir" ]; then
        OUTPUT_DIR="dist/$APP_NAME"
    else
        OUTPUT_DIR="dist"
    fi

    if command -v strip &> /dev/null; then
        find "$OUTPUT_DIR" -type f \( -name "*.so*" -o -name "*.pyd" -o -perm /111 \) \
            -exec strip --strip-unneeded {} + 2>/dev/null || true
        echo "  Binaries stripped"
    else
        echo "  strip not found, skipping"
    fi
else
    echo "  Skipping strip (--no-strip specified)"
fi

# Step 8: Create archive
echo ""
echo "==> [8/8] Creating distribution archive"

if [ "$MODE" == "--onedir" ]; then
    ARCHIVE_NAME="$APP_NAME-$(date +%Y%m%d)-linux-x64.tar.gz"
    cd dist
    tar -czf "$ARCHIVE_NAME" "$APP_NAME"
    cd ..
    echo "  Archive: dist/$ARCHIVE_NAME"
fi

# Done
echo ""
echo "=============================================="
echo "  Build Complete!"
echo "=============================================="

if [ "$MODE" == "--onedir" ]; then
    OUTPUT="dist/$APP_NAME"
else
    OUTPUT="dist/$APP_NAME"
fi

SIZE=$(du -sh "$OUTPUT" 2>/dev/null | cut -f1 || echo "unknown")

echo ""
echo "Output: $OUTPUT"
echo "Size: $SIZE"
echo ""
echo "To run: cd ${OUTPUT%/*} && ./$APP_NAME"
echo ""
echo "Tip: If plugins are missing, run:"
echo "  ./collect_qt_plugins.sh"
echo "  python scripts/extract_qt_plugins.py"
echo "  ./build_uv.sh"
echo ""
