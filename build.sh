#!/bin/bash
#
# Harmony Music Player - Unified Build Script
# Automatically detects platform and builds accordingly
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="Harmony"
APP_VERSION="1.0.0"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}=========================================${NC}"
    echo -e "${BLUE}  $APP_NAME v$APP_VERSION - Build System${NC}"
    echo -e "${BLUE}=========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

detect_platform() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "macos";;
        CYGWIN*|MINGW*|MSYS*)    echo "windows";;
        *)          echo "unknown";;
    esac
}

check_dependencies() {
    print_info "Checking dependencies..."

    # Check Python
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        print_error "Python is not installed"
        exit 1
    fi

    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1)
    print_success "Python: $PYTHON_VERSION"

    # Check pip
    if ! $PYTHON_CMD -m pip --version &> /dev/null; then
        print_error "pip is not installed"
        exit 1
    fi
    print_success "pip is available"

    # Install PyInstaller if needed
    if ! $PYTHON_CMD -c "import PyInstaller" 2>/dev/null; then
        print_info "Installing PyInstaller..."
        $PYTHON_CMD -m pip install pyinstaller
    fi
    print_success "PyInstaller is available"
}

build_project() {
    local platform=$(detect_platform)
    print_info "Detected platform: $platform"
    print_info "Building for: $platform"

    case "$platform" in
        linux)
            chmod +x "$SCRIPT_DIR/build_linux.sh"
            "$SCRIPT_DIR/build_linux.sh" "$@"
            ;;
        macos)
            chmod +x "$SCRIPT_DIR/build_macos.sh"
            "$SCRIPT_DIR/build_macos.sh" "$@"
            ;;
        windows)
            if command -v pwsh &> /dev/null; then
                pwsh -File "$SCRIPT_DIR/build_windows.ps1"
            else
                cmd.exe /c "$SCRIPT_DIR\build_windows.bat"
            fi
            ;;
        *)
            print_error "Unsupported platform: $platform"
            print_info "Using Python build script directly..."
            $PYTHON_CMD build.py
            ;;
    esac
}

# Main
print_header
check_dependencies
build_project "$@"
print_success "Build complete!"
