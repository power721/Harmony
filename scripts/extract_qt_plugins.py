#!/usr/bin/env python3
"""
Extract Qt plugins from debug log to create a whitelist.

Usage: python scripts/extract_qt_plugins.py

Input: build_analysis/qt_plugins.log
Output: build_analysis/qt_plugins_whitelist.txt
"""

import platform
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
LOG_FILE = PROJECT_ROOT / "build_analysis" / "qt_plugins.log"
OUTPUT_FILE = PROJECT_ROOT / "build_analysis" / "qt_plugins_whitelist.txt"

# Platform-specific required plugins
PLATFORM_PLUGINS = {
    "Linux": [
        # X11 platform (essential)
        "platforms/libqxcb.so",
        # Wayland support
        "platforms/libqwayland.so",
        "platforms/libqwayland-generic.so",
        # Minimal/offscreen for headless
        "platforms/libqoffscreen.so",
        "platforms/libqminimal.so",
        # Input methods (Chinese users)
        "platforminputcontexts/libfcitx5platforminputcontextplugin.so",
        "platforminputcontexts/libfcitxplatforminputcontextplugin.so",
        "platforminputcontexts/libibusplatforminputcontextplugin.so",
        # Platform themes
        "platformthemes/libqgtk3.so",
        "platformthemes/libqxdgdesktopportal.so",
        # Multimedia - FFmpeg backend (PySide6 6.5+)
        "multimedia/libffmpegmediaplugin.so",
        # Multimedia - GStreamer backend (PySide6 6.4.x or with GST installed)
        "mediaservice/libgstmediaplayer.so",
        "mediaservice/libgstaudiodecoder.so",
        # XCB GL integrations
        "xcbglintegrations/libqxcb-glx-integration.so",
        "xcbglintegrations/libqxcb-egl-integration.so",
    ],
    "Darwin": [  # macOS
        "platforms/libqcocoa.so",
        "platforms/libqminimal.so",
        "platforms/libqoffscreen.so",
        # Multimedia - AVFoundation (older PySide6)
        "mediaservice/libqavfmediaplayer.so",
        "mediaservice/libqavfcamera.so",
        # Multimedia - FFmpeg backend (PySide6 6.5+)
        "multimedia/libffmpegmediaplugin.so",
    ],
    "Windows": [
        "platforms/qwindows.dll",
        "platforms/qminimal.dll",
        "platforms/qoffscreen.dll",
        # Multimedia - Windows Media Foundation
        "mediaservice/wmfservice.dll",
        # Multimedia - FFmpeg backend (PySide6 6.5+)
        "multimedia/ffmpegmediaplugin.dll",
        # Windows styles
        "styles/qwindowsvistastyle.dll",
    ],
}

# Common plugins (all platforms)
COMMON_PLUGINS = [
    # Image formats
    "imageformats/libqjpeg.so",
    "imageformats/libqpng.so",
    "imageformats/libqgif.so",
    "imageformats/libqico.so",
    "imageformats/libqsvg.so",
    "imageformats/qjpeg.dll",
    "imageformats/qpng.dll",
    "imageformats/qgif.dll",
    "imageformats/qico.dll",
    "imageformats/qsvg.dll",
    # Icon engine
    "iconengines/libqsvgicon.so",
    "iconengines/qsvgicon.dll",
]


def get_platform_name() -> str:
    """Get platform name for plugin selection."""
    system = platform.system()
    if system == "Linux":
        return "Linux"
    elif system == "Darwin":
        return "Darwin"
    elif system == "Windows":
        return "Windows"
    return "Linux"  # Default


def extract_plugins(log_path: Path) -> set[str]:
    """Extract loaded plugins from Qt debug log."""
    plugins = set()

    # Pattern: loaded library ".../plugins/xxx/yyy.so" or ".../plugins/xxx/yyy.dll"
    pattern = re.compile(
        r'loaded library ["\']?(.+?/plugins/(.+?\.(?:so|dll))[^"\']*)?["\']?',
        re.IGNORECASE
    )

    if not log_path.exists():
        print(f"Warning: Log file not found: {log_path}")
        return plugins

    with open(log_path, "r", errors="ignore") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                full_path = match.group(1)
                if not full_path:
                    continue
                # Extract relative path from plugins/
                if "plugins/" in full_path:
                    relative = full_path.split("plugins/")[-1]
                    # Normalize path
                    relative = relative.rstrip('"\'').strip()
                    plugins.add(relative)
                    print(f"  Found: {relative}")

    return plugins


def main():
    print("=" * 50)
    print("  Qt Plugin Whitelist Generator")
    print("=" * 50)
    print()

    current_platform = get_platform_name()
    print(f"==> Current platform: {current_platform}")

    # Extract from log
    print(f"\n==> Reading: {LOG_FILE}")
    plugins = extract_plugins(LOG_FILE)

    # Add platform-specific required plugins
    platform_plugins = PLATFORM_PLUGINS.get(current_platform, [])
    print(f"\n==> Adding {len(platform_plugins)} platform-specific plugins for {current_platform}")
    for plugin in platform_plugins:
        plugins.add(plugin)
        print(f"  Required: {plugin}")

    # Add common plugins
    print(f"\n==> Adding {len(COMMON_PLUGINS)} common plugins")
    for plugin in COMMON_PLUGINS:
        plugins.add(plugin)

    # Filter to only include plugins that exist for current platform extension
    if current_platform == "Windows":
        plugins = {p for p in plugins if p.endswith(".dll") or "/" not in p}
    else:
        plugins = {p for p in plugins if p.endswith(".so") or "\\" not in p}

    # Write whitelist
    print(f"\n==> Writing whitelist: {OUTPUT_FILE}")
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w") as f:
        for plugin in sorted(plugins):
            f.write(plugin + "\n")

    print(f"\n==> Total plugins in whitelist: {len(plugins)}")

    # Print summary
    print("\nWhitelist summary:")
    categories = {}
    for plugin in plugins:
        category = plugin.split("/")[0] if "/" in plugin else "other"
        categories[category] = categories.get(category, 0) + 1

    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

    # Critical check
    print("\n==> Critical multimedia plugins check:")
    multimedia_plugins = [p for p in plugins if "multimedia" in p or "mediaservice" in p]
    if multimedia_plugins:
        for p in multimedia_plugins:
            print(f"  ✓ {p}")
    else:
        print("  ✗ WARNING: No multimedia plugins found!")
        print("    Audio playback may not work!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
