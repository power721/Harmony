#!/bin/bash
#
# Harmony Music Player - Unified Build Script
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="Harmony"
APP_VERSION="${APP_VERSION:-1.0.0}"

echo "========================================"
echo "  $APP_NAME v$APP_VERSION - Build"
echo "========================================"

detect_platform() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "macos";;
        CYGWIN*|MINGW*|MSYS*)    echo "windows";;
        *)          echo "unknown";;
    esac
}

PLATFORM=$(detect_platform)
echo "Platform: $PLATFORM"

case "$PLATFORM" in
    linux)
        echo "Building Linux packages..."
        chmod +x build_linux.sh
        ./build_linux.sh "$@"
        ;;
    macos)
        echo "Building macOS app..."
        chmod +x build_macos.sh
        ./build_macos.sh "$@"
        ;;
    windows)
        echo "Building Windows executable..."
        if command -v pwsh &> /dev/null; then
            pwsh -File build_windows.ps1
        else
            cmd.exe /c build_windows.bat
        fi
        ;;
    *)
        echo "Unknown platform, using build.py..."
        uv run python build.py
        ;;
esac

echo ""
echo "Build complete!"
