#!/usr/bin/env python3
"""
Harmony Music Player - Cross-platform Build Script
Builds executable for Linux, macOS, and Windows using PyInstaller.

Usage:
    python build.py [platform]

    platform: linux, macos, windows, or current (default: current)
"""

import os
import sys
import platform
import subprocess
import shutil
import argparse
from pathlib import Path
from datetime import datetime

# Project info
APP_NAME = "Harmony"
APP_VERSION = "1.0.0"
AUTHOR = "Harmony Player"
DESCRIPTION = "Modern Music Player with Spotify-like Interface"

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.resolve()
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"


def get_platform_info(target_platform: str = None) -> dict:
    """Get platform-specific build configuration."""
    current_system = platform.system().lower()

    if target_platform is None or target_platform == "current":
        target_platform = current_system

    platform_info = {
        "linux": {
            "system": "Linux",
            "extension": "",
            "icon_extension": ".png",
            "onefile_options": [],
            "onedir_options": [],
            "extra_datas": [],
            "extra_binaries": [],
        },
        "darwin": {
            "system": "macOS",
            "extension": ".app",
            "icon_extension": ".icns",
            "onefile_options": [
                "--osx-bundle-identifier",
                f"com.harmonyplayer.{APP_NAME.lower()}",
            ],
            "onedir_options": [
                "--osx-bundle-identifier",
                f"com.harmonyplayer.{APP_NAME.lower()}",
            ],
            "extra_datas": [],
            "extra_binaries": [],
        },
        "windows": {
            "system": "Windows",
            "extension": ".exe",
            "icon_extension": ".ico",
            "onefile_options": [
                "--noconsole",
                "--uac-admin",
            ],
            "onedir_options": [
                "--noconsole",
            ],
            "extra_datas": [],
            "extra_binaries": [],
        },
    }

    if target_platform in platform_info:
        return platform_info[target_platform]
    else:
        print(f"Warning: Unknown platform '{target_platform}', using current system")
        return platform_info.get(current_system, platform_info["linux"])


def find_icon(platform_name: str) -> Path:
    """Find icon file for the platform."""
    icon_extension = {
        "linux": ".png",
        "darwin": ".icns",
        "windows": ".ico",
    }.get(platform_name, ".png")

    # Check common icon locations
    icon_paths = [
        PROJECT_ROOT / f"icons{icon_extension}",
        PROJECT_ROOT / "icons" / f"icon{icon_extension}",
        PROJECT_ROOT / "resources" / f"icon{icon_extension}",
        PROJECT_ROOT / "assets" / f"icon{icon_extension}",
        PROJECT_ROOT / f"{APP_NAME.lower()}{icon_extension}",
    ]

    for icon_path in icon_paths:
        if icon_path.exists():
            return icon_path

    return None


def collect_data_files() -> list:
    """Collect additional data files to include."""
    datas = []

    # Translations
    translations_dir = PROJECT_ROOT / "translations"
    if translations_dir.exists():
        datas.append((str(translations_dir), "translations"))

    # Add more data directories as needed
    data_dirs = ["assets", "resources", "icons", "themes"]
    for data_dir in data_dirs:
        dir_path = PROJECT_ROOT / data_dir
        if dir_path.exists():
            datas.append((str(dir_path), data_dir))

    return datas


def clean_build_dirs():
    """Clean build and dist directories."""
    print("Cleaning build directories...")
    for dir_path in [BUILD_DIR, DIST_DIR]:
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"  Removed: {dir_path}")


def check_pyinstaller():
    """Check if PyInstaller is installed and apply conda fix if needed."""
    # Fix conda compatibility issue BEFORE importing PyInstaller
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        print(f"Conda environment detected: {conda_prefix}")
        print("Setting PYINSTALLER_NO_CONDA=1 for compatibility")
        os.environ["PYINSTALLER_NO_CONDA"] = "1"

    try:
        import PyInstaller

        print(f"PyInstaller version: {PyInstaller.__version__}")
        return True
    except ImportError:
        print("Error: PyInstaller is not installed.")
        print("Please install it with: pip install pyinstaller")
        return False


def check_conda_env():
    """Check if running in a conda environment."""
    conda_prefix = os.environ.get("CONDA_PREFIX")
    return conda_prefix is not None


def build_executable(
    platform_name: str = None,
    one_file: bool = True,
    clean: bool = True,
    debug: bool = False,
):
    """Build the executable using PyInstaller."""
    if not check_pyinstaller():
        return False

    # Get platform info
    platform_info = get_platform_info(platform_name)
    target_platform = platform_name or platform.system().lower()

    print(f"\nBuilding for {platform_info['system']}...")
    print(f"Target platform: {target_platform}")
    print(f"Mode: {'Single file' if one_file else 'Directory'}")

    # Clean if requested
    if clean:
        clean_build_dirs()

    # Build PyInstaller command
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        APP_NAME,
        "--noconfirm",
    ]

    # Single file or directory mode
    if one_file:
        cmd.append("--onefile")
        cmd.extend(platform_info.get("onefile_options", []))
    else:
        cmd.append("--onedir")
        cmd.extend(platform_info.get("onedir_options", []))

    # Add icon if available
    icon_path = find_icon(target_platform)
    if icon_path:
        cmd.extend(["--icon", str(icon_path)])
        print(f"Using icon: {icon_path}")
    else:
        print("No icon found, building without icon")

    # Add data files
    data_files = collect_data_files()
    for src, dst in data_files:
        cmd.extend(["--add-data", f"{src}{os.pathsep}{dst}"])
        print(f"Adding data: {src} -> {dst}")

    # Add hidden imports for PySide6
    hidden_imports = [
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtMultimedia",
        "PySide6.QtNetwork",
        "PySide6.QtSvg",
        "mutagen",
        "mutagen.easyid3",
        "mutagen.id3",
        "mutagen.flac",
        "mutagen.ogg",
        "mutagen.oggflac",
        "mutagen.oggopus",
        "mutagen.oggvorbis",
        "mutagen.mp4",
        "mutagen.asf",
        "mutagen.apev2",
        "mutagen.musepack",
        "mutagen.optimfrog",
        "mutagen.trueaudio",
        "mutagen.wavpack",
        "mutagen.dsf",
        "mutagen.dsd",
        "mutagen.smf",
        "mutagen.aac",
        "mutagen.ac3",
        "mutagen.aiff",
        "mutagen.monkeysaudio",
        "mutagen.musepack",
        "mutagen.oggflac",
        "mutagen.oggopus",
        "mutagen.oggvorbis",
        "mutagen.optimfrog",
        "mutagen.trueaudio",
        "mutagen.wavpack",
        "requests",
        "bs4",
        "lxml",
        "lxml.etree",
        "lxml._elementpath",
        "PIL",
        "PIL._imaging",
        "qrcode",
        "qrcode.util",
        "qrcode.image.pil",
        "qrcode.image.svg",
        "pymediainfo",
    ]

    for hidden_import in hidden_imports:
        cmd.extend(["--hidden-import", hidden_import])

    # Exclude unnecessary modules to reduce size
    excludes = [
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "pytest",
        "sphinx",
        "docutils",
        "IPython",
        "jupyter",
        "notebook",
        "torch",
        "tensorflow",
        "keras",
        "cv2",
        "opencv",
        "PyQt5",
        "PyQt6",
        "PyQt4",
        "PySide2",
        "PySide",
        "wx",
        "gtk",
        "PyObjCTools",
        "objc",
        "Foundation",
        "AppKit",
        "CoreFoundation",
        "Quartz",
    ]

    for exclude in excludes:
        cmd.extend(["--exclude-module", exclude])

    # Debug mode
    if debug:
        cmd.append("--debug=all")
        cmd.append("--log-level=DEBUG")
    else:
        cmd.append("--log-level=WARN")

    # Work paths
    cmd.extend(["--workpath", str(BUILD_DIR)])
    cmd.extend(["--distpath", str(DIST_DIR)])
    cmd.extend(["--specpath", str(PROJECT_ROOT)])

    # Main script
    cmd.append(str(PROJECT_ROOT / "main.py"))

    print("\nRunning PyInstaller...")
    print(f"Command: {' '.join(cmd[:10])}...")  # Print first 10 args

    try:
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True)
        print("\n✓ Build completed successfully!")

        # Print output location
        output_name = APP_NAME + platform_info["extension"]
        if one_file:
            output_path = DIST_DIR / output_name
        else:
            output_path = DIST_DIR / APP_NAME / output_name

        print(f"Output: {output_path}")

        # Create version info file
        create_version_file()

        return True

    except subprocess.CalledProcessError as e:
        print(f"\n✗ Build failed with error: {e}")
        return False


def create_version_file():
    """Create a VERSION file in the dist directory."""
    version_info = f"""{APP_NAME} v{APP_VERSION}
Built on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Platform: {platform.system()} {platform.release()}
Python: {platform.python_version()}

{DESCRIPTION}
"""

    version_path = DIST_DIR / "VERSION.txt"
    with open(version_path, "w") as f:
        f.write(version_info)
    print(f"Version info written to: {version_path}")


def create_readme():
    """Create a README for the distribution."""
    readme_content = f"""# {APP_NAME} v{APP_VERSION}

{DESCRIPTION}

## System Requirements

### Linux
- glibc 2.17 or later
- X11 or Wayland display server
- PulseAudio or PipeWire audio system
- Required libraries: libxcb, libxkbcommon, libgl1

### macOS
- macOS 10.14 (Mojave) or later
- Intel or Apple Silicon (Universal Binary)

### Windows
- Windows 10 or later
- Visual C++ Redistributable 2015-2022

## Installation

### Linux
```bash
chmod +x {APP_NAME}
./{APP_NAME}
```

### macOS
1. Open the .dmg file
2. Drag {APP_NAME}.app to Applications folder
3. Open from Applications (may need to allow in Security settings)

### Windows
1. Run {APP_NAME}.exe
2. Windows may show a security warning - click "More info" then "Run anyway"

## Features

- Modern Spotify-like interface
- Support for multiple audio formats (MP3, FLAC, OGG, M4A, WAV, WMA)
- Playlist management
- Lyrics display with LRC support
- Album art fetching
- Cloud drive integration (Quark Drive)
- Global hotkeys
- Mini player mode
- Audio equalizer

## License

This software is provided as-is. See LICENSE file for details.

## Support

For issues and feature requests, please visit the project repository.

Built with PySide6 (Qt6) and Python {platform.python_version()}
"""

    readme_path = DIST_DIR / "README.txt"
    with open(readme_path, "w") as f:
        f.write(readme_content)
    print(f"README written to: {readme_path}")


def main():
    parser = argparse.ArgumentParser(
        description=f"Build {APP_NAME} executable for different platforms"
    )
    parser.add_argument(
        "platform",
        nargs="?",
        default="current",
        choices=["linux", "macos", "windows", "current"],
        help="Target platform (default: current)",
    )
    parser.add_argument(
        "--dir",
        action="store_true",
        help="Build as directory instead of single file",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Don't clean build directories before building",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode for troubleshooting",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Build for all platforms (requires appropriate environment)",
    )

    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"  {APP_NAME} v{APP_VERSION} - Build Script")
    print(f"{'='*60}")

    if args.all:
        # Build for all platforms
        for platform_name in ["linux", "macos", "windows"]:
            build_executable(
                platform_name=platform_name,
                one_file=not args.dir,
                clean=args.no_clean is False,
                debug=args.debug,
            )
    else:
        # Build for single platform
        target = None if args.platform == "current" else args.platform
        success = build_executable(
            platform_name=target,
            one_file=not args.dir,
            clean=args.no_clean is False,
            debug=args.debug,
        )

        if success:
            create_readme()

    print("\nDone!")


if __name__ == "__main__":
    main()
