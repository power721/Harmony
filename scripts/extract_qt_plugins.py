#!/usr/bin/env python3
"""
Extract Qt plugins from debug log to create a whitelist.

Usage: python scripts/extract_qt_plugins.py

Input: build_analysis/qt_plugins.log
Output: build_analysis/qt_plugins_whitelist.txt
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
LOG_FILE = PROJECT_ROOT / "build_analysis" / "qt_plugins.log"
OUTPUT_FILE = PROJECT_ROOT / "build_analysis" / "qt_plugins_whitelist.txt"

# Always-required plugins (manual additions)
REQUIRED_PLUGINS = [
    # Linux X11 platform (essential)
    "platforms/libqxcb.so",
    # Wayland support (common on modern Linux)
    "platforms/libqwayland.so",
    "platforms/libqwayland-generic.so",
    # Minimal/offscreen for headless scenarios
    "platforms/libqoffscreen.so",
    "platforms/libqminimal.so",
    # Common image formats
    "imageformats/libqjpeg.so",
    "imageformats/libqpng.so",
    "imageformats/libqgif.so",
    "imageformats/libqico.so",
    "imageformats/libqsvg.so",
    # Icon engine
    "iconengines/libqsvgicon.so",
    # Input methods (Chinese users need these)
    "platforminputcontexts/libfcitx5platforminputcontextplugin.so",
    "platforminputcontexts/libfcitxplatforminputcontextplugin.so",
    "platforminputcontexts/libibusplatforminputcontextplugin.so",
    # Multimedia (for music player) - CRITICAL!
    # This is the actual ffmpeg backend plugin that Qt loads at runtime
    "multimedia/libffmpegmediaplugin.so",
]


def extract_plugins(log_path: Path) -> set[str]:
    """Extract loaded plugins from Qt debug log."""
    plugins = set()

    # Pattern: loaded library ".../plugins/xxx/yyy.so"
    pattern = re.compile(r'loaded library ["\']?(.+?/plugins/(.+?\.so[^"\']*)?)["\']?', re.IGNORECASE)

    if not log_path.exists():
        print(f"Warning: Log file not found: {log_path}")
        return plugins

    with open(log_path, "r", errors="ignore") as f:
        for line in f:
            match = pattern.search(line)
            if match and not "libqwayland" in match.group(1):
                full_path = match.group(1)
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

    # Extract from log
    print(f"==> Reading: {LOG_FILE}")
    plugins = extract_plugins(LOG_FILE)

    # Add required plugins
    print(f"\n==> Adding {len(REQUIRED_PLUGINS)} required plugins")
    for plugin in REQUIRED_PLUGINS:
        plugins.add(plugin)
        print(f"  Required: {plugin}")

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

    return 0


if __name__ == "__main__":
    sys.exit(main())
