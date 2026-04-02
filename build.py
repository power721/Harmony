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
import glob
from pathlib import Path
from datetime import datetime
import os
import sys
from PySide6.QtCore import QCoreApplication

# This helps the .exe find the 'plugins' folder included by PyInstaller
if getattr(sys, 'frozen', False):
    app_path = os.path.dirname(sys.executable)
    # Point Qt to the internal PySide6 plugins folder
    plugin_path = os.path.join(app_path, "PySide6", "plugins")
    QCoreApplication.addLibraryPath(plugin_path)

# Project info
APP_NAME = "Harmony"
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
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
        PROJECT_ROOT / f"icon{icon_extension}",
        PROJECT_ROOT / f"icons{icon_extension}",
        PROJECT_ROOT / "icons" / f"icon{icon_extension}",
        PROJECT_ROOT / "resources" / f"icon{icon_extension}",
        PROJECT_ROOT / "assets" / f"icon{icon_extension}",
        PROJECT_ROOT / f"{APP_NAME.lower()}{icon_extension}",
    ]

    for icon_path in icon_paths:
        if icon_path.exists():
            return icon_path

    # If platform-specific icon not found, try to generate from PNG
    if platform_name in ("darwin", "windows"):
        png_icon = find_png_icon()
        if png_icon:
            generated_icon = generate_icon(png_icon, platform_name)
            if generated_icon:
                return generated_icon

    return None


def find_png_icon() -> Path:
    """Find PNG icon file for conversion."""
    png_paths = [
        PROJECT_ROOT / "icon.png",
        PROJECT_ROOT / "icons.png",
        PROJECT_ROOT / "icons" / "icon.png",
        PROJECT_ROOT / "resources" / "icon.png",
        PROJECT_ROOT / "assets" / "icon.png",
        PROJECT_ROOT / f"{APP_NAME.lower()}.png",
    ]
    for png_path in png_paths:
        if png_path.exists():
            return png_path
    return None


def generate_icon(png_path: Path, platform_name: str) -> Path:
    """Generate platform-specific icon from PNG."""
    output_dir = PROJECT_ROOT / "icons"
    output_dir.mkdir(exist_ok=True)

    if platform_name == "windows":
        output_path = output_dir / "icon.ico"
        if output_path.exists():
            return output_path
        return generate_ico(png_path, output_path)
    elif platform_name == "darwin":
        output_path = output_dir / "icon.icns"
        if output_path.exists():
            return output_path
        return generate_icns(png_path, output_path)

    return None


def generate_ico(png_path: Path, output_path: Path) -> Path:
    """Generate ICO file from PNG using Pillow."""
    try:
        from PIL import Image

        print(f"Generating ICO from {png_path}...")
        img = Image.open(png_path)

        # Generate multiple sizes for ICO
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        icons = []
        for size in sizes:
            resized = img.resize(size, Image.Resampling.LANCZOS)
            icons.append(resized)

        # Save as ICO with multiple sizes
        icons[0].save(
            output_path,
            format="ICO",
            sizes=[(i.width, i.height) for i in icons],
            append_images=icons[1:],
        )
        print(f"Generated: {output_path}")
        return output_path

    except ImportError:
        print("Warning: Pillow not installed, cannot generate ICO. Install with: pip install Pillow")
        return None
    except Exception as e:
        print(f"Warning: Failed to generate ICO: {e}")
        return None


def generate_icns(png_path: Path, output_path: Path) -> Path:
    """Generate ICNS file from PNG."""
    try:
        from PIL import Image
        import tempfile
        import shutil

        print(f"Generating ICNS from {png_path}...")
        img = Image.open(png_path)

        # Create temporary iconset directory
        iconset_dir = output_path.parent / "icon.iconset"
        iconset_dir.mkdir(exist_ok=True)

        # ICNS requires specific sizes with specific names
        size_map = {
            "icon_16x16.png": 16,
            "icon_16x16@2x.png": 32,
            "icon_32x32.png": 32,
            "icon_32x32@2x.png": 64,
            "icon_128x128.png": 128,
            "icon_128x128@2x.png": 256,
            "icon_256x256.png": 256,
            "icon_256x256@2x.png": 512,
            "icon_512x512.png": 512,
            "icon_512x512@2x.png": 1024,
        }

        for filename, size in size_map.items():
            resized = img.resize((size, size), Image.Resampling.LANCZOS)
            resized.save(iconset_dir / filename)

        # Use iconutil on macOS, or just use the PNG directly
        if platform.system() == "Darwin":
            subprocess.run(
                ["iconutil", "-c", "icns", "-o", str(output_path), str(iconset_dir)],
                check=True,
            )
            print(f"Generated: {output_path}")
        else:
            # On non-macOS, we can't create proper ICNS, use PNG fallback
            print("Warning: ICNS generation requires macOS. Using PNG fallback.")
            shutil.rmtree(iconset_dir)
            return None

        # Clean up
        shutil.rmtree(iconset_dir)
        return output_path

    except ImportError:
        print("Warning: Pillow not installed, cannot generate ICNS. Install with: pip install Pillow")
        return None
    except Exception as e:
        print(f"Warning: Failed to generate ICNS: {e}")
        return None


def collect_data_files() -> list:
    """Collect additional data files to include."""
    datas = []

    # Translations
    translations_dir = PROJECT_ROOT / "translations"
    if translations_dir.exists():
        datas.append((str(translations_dir), "translations"))

    # UI styles (QSS files)
    ui_styles_dir = PROJECT_ROOT / "ui"
    if ui_styles_dir.exists():
        datas.append((str(ui_styles_dir), "ui"))
        print(f"[INFO] Found UI styles: {ui_styles_dir}")

    # Application icon (for packaged executable)
    icon_file = PROJECT_ROOT / "icon.png"
    if icon_file.exists():
        datas.append((str(icon_file), "."))
        print(f"[INFO] Found icon: {icon_file}")

    # Add more data directories as needed
    data_dirs = ["assets", "resources", "icons", "themes", "fonts"]
    for data_dir in data_dirs:
        dir_path = PROJECT_ROOT / data_dir
        if dir_path.exists():
            datas.append((str(dir_path), data_dir))
            print(f"[INFO] Found {data_dir}: {dir_path}")
        else:
            print(f"[WARN] {data_dir} directory not found: {dir_path}")

    return datas


def collect_ssl_certificates() -> list:
    """Collect SSL certificates for HTTPS connections."""
    datas = []

    # Use collect_data_files for certifi
    try:
        from PyInstaller.utils.hooks import collect_data_files
        datas += collect_data_files("certifi")
        print("Added certifi data files via collect_data_files")
    except Exception as e:
        print(f"Warning: Could not collect certifi data files: {e}")
        # Fallback: try to find certifi certificates manually
        try:
            import certifi
            cert_path = Path(certifi.where())
            if cert_path.exists():
                datas.append((str(cert_path), "certifi"))
                print(f"Found certifi certificates: {cert_path}")
        except ImportError:
            print("Warning: certifi not installed, SSL may not work properly")

    # Also try to find system certificates (Linux)
    system_cert_paths = [
        "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu
        "/etc/pki/tls/certs/ca-bundle.crt",    # RHEL/CentOS
        "/etc/ssl/ca-bundle.pem",               # OpenSUSE
        "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",  # Fedora
    ]

    for cert_path in system_cert_paths:
        if Path(cert_path).exists():
            datas.append((cert_path, "certs"))
            print(f"Found system certificates: {cert_path}")
            break

    return datas


def collect_hidden_imports() -> list:
    """Collect hidden imports using PyInstaller's collect_submodules."""
    hiddenimports = []

    try:
        from PyInstaller.utils.hooks import collect_submodules

        # 网络请求相关 - 自动收集所有子模块
        for package in ["requests", "urllib3", "certifi", "charset_normalizer", "idna"]:
            try:
                hiddenimports += collect_submodules(package)
                print(f"Collected submodules for: {package}")
            except Exception as e:
                print(f"Warning: Could not collect submodules for {package}: {e}")

        # 音频元数据
        try:
            hiddenimports += collect_submodules("mutagen")
            print("Collected submodules for: mutagen")
        except Exception as e:
            print(f"Warning: Could not collect mutagen submodules: {e}")

        # QQ音乐 API
        try:
            hiddenimports += collect_submodules("qqmusic_api")
            print("Collected submodules for: qqmusic_api")
        except Exception as e:
            print(f"Warning: Could not collect qqmusic_api submodules: {e}")

        # 其他依赖
        for package in ["PIL", "qrcode", "bs4", "lxml"]:
            try:
                hiddenimports += collect_submodules(package)
                print(f"Collected submodules for: {package}")
            except Exception as e:
                print(f"Warning: Could not collect submodules for {package}: {e}")

    except ImportError:
        print("Warning: PyInstaller hooks not available, using fallback list")
        # Fallback to manual list
        hiddenimports = get_fallback_hidden_imports()

    # 添加核心模块
    hiddenimports += [
        "ssl",
        "_ssl",
        "mpv",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtMultimedia",
        "PySide6.QtNetwork",
        "PySide6.QtSvg",
    ]

    # 去重
    return list(set(hiddenimports))


def get_fallback_hidden_imports() -> list:
    """Fallback hidden imports list if collect_submodules is not available."""
    return [
        "requests", "urllib3", "certifi", "charset_normalizer", "idna",
        "mutagen", "mutagen.easyid3", "mutagen.id3", "mutagen.flac",
        "mutagen.ogg", "mutagen.oggflac", "mutagen.oggopus", "mutagen.oggvorbis",
        "mutagen.mp4", "mutagen.asf", "mutagen.apev2", "mutagen.musepack",
        "mutagen.optimfrog", "mutagen.trueaudio", "mutagen.wavpack",
        "mutagen.dsf", "mutagen.dsd", "mutagen.smf", "mutagen.aac",
        "mutagen.ac3", "mutagen.aiff", "mutagen.monkeysaudio",
        "PIL", "PIL._imaging", "qrcode", "qrcode.util",
        "qrcode.image.pil", "qrcode.image.svg",
        "bs4", "lxml", "lxml.etree", "lxml._elementpath",
    ]


def find_openssl_libs() -> list:
    """自动查找OpenSSL动态库 - 优先使用Python _ssl模块实际链接的库"""
    binaries = []

    # 方法1: 通过 _ssl 模块获取实际链接的SSL库
    try:
        import _ssl
        ssl_so = _ssl.__file__
        result = subprocess.run(
            ["ldd", ssl_so],
            capture_output=True,
            text=True,
            timeout=10
        )

        for line in result.stdout.splitlines():
            if "libssl.so" in line or "libcrypto.so" in line:
                parts = line.split("=>")
                if len(parts) >= 2:
                    lib_path = parts[1].split("(")[0].strip()
                    # 规范化路径（处理 ../ 等）
                    lib_path = os.path.normpath(lib_path)
                    if os.path.exists(lib_path):
                        binaries.append((lib_path, "."))
                        print(f"[INFO] Found Python's OpenSSL: {lib_path}")

    except Exception as e:
        print(f"[WARN] Could not detect Python's SSL libs via ldd: {e}")

    # 方法2: 检查conda/miniforge环境
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        conda_libs = [
            os.path.join(conda_prefix, "lib", "libssl.so.3"),
            os.path.join(conda_prefix, "lib", "libcrypto.so.3"),
            os.path.join(conda_prefix, "lib", "libssl.so.1.1"),
            os.path.join(conda_prefix, "lib", "libcrypto.so.1.1"),
        ]
        for lib_path in conda_libs:
            if os.path.exists(lib_path) and (lib_path, ".") not in binaries:
                binaries.append((lib_path, "."))
                print(f"[INFO] Found Conda OpenSSL: {lib_path}")

    # 方法3: 系统库作为备选
    if not binaries:
        print("[WARN] No Python-linked SSL found, falling back to system libs")
        possible_paths = [
            # Ubuntu 22.04+ / Debian (OpenSSL 3.x)
            "/usr/lib/x86_64-linux-gnu/libssl.so.3",
            "/usr/lib/x86_64-linux-gnu/libcrypto.so.3",
            # Ubuntu 20.04 / Debian (OpenSSL 1.1)
            "/usr/lib/x86_64-linux-gnu/libssl.so.1.1",
            "/usr/lib/x86_64-linux-gnu/libcrypto.so.1.1",
            # Fedora / RHEL
            "/usr/lib64/libssl.so.3",
            "/usr/lib64/libcrypto.so.3",
            "/usr/lib64/libssl.so.1.1",
            "/usr/lib64/libcrypto.so.1.1",
            # Arch Linux
            "/usr/lib/libssl.so.3",
            "/usr/lib/libcrypto.so.3",
        ]

        for lib_path in possible_paths:
            if os.path.exists(lib_path):
                binaries.append((lib_path, "."))
                print(f"[INFO] Found System OpenSSL: {lib_path}")

    # 去重
    return list(set(binaries))


def find_qt_plugins() -> list:
    """收集Qt插件目录"""
    binaries = []

    # 获取PySide6插件路径
    try:
        from PySide6.QtCore import QLibraryInfo
        qt_plugins = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
        print(f"[INFO] Qt plugins path: {qt_plugins}")

        # 需要打包的Qt插件目录
        # platforminputcontexts: 输入法支持 (fcitx5, ibus等)
        plugin_dirs = [
            "platforms",
            "platforminputcontexts",  # 输入法插件
            "imageformats",
            "multimedia",
            "audio",
            "mediaservice",
            "platformthemes",  # 平台主题
            "xcbglintegrations",  # XCB OpenGL集成
        ]

        for plugin_name in plugin_dirs:
            plugin_path = os.path.join(qt_plugins, plugin_name)
            if os.path.exists(plugin_path):
                binaries.append((plugin_path, f"PySide6/Qt/plugins/{plugin_name}"))
                print(f"[INFO] Found Qt plugin: {plugin_name}")
            else:
                print(f"[WARN] Qt plugin not found: {plugin_name}")

    except Exception as e:
        print(f"Warning: Could not find Qt plugins: {e}")

    return binaries


def find_ffmpeg_libs() -> list:
    """查找FFmpeg库（QtMultimedia依赖）"""
    binaries = []

    if platform.system() != "Linux":
        return binaries

    ffmpeg_libs = ["libavcodec", "libavformat", "libavutil", "libswresample", "libswscale"]

    for lib_name in ffmpeg_libs:
        patterns = [
            f"/usr/lib/x86_64-linux-gnu/{lib_name}.so*",
            f"/usr/lib64/{lib_name}.so*",
            f"/usr/lib/{lib_name}.so*",
        ]
        for pattern in patterns:
            matches = glob.glob(pattern)
            if matches:
                # 只取第一个匹配（通常是最新版本）
                binaries.append((matches[0], "."))
                print(f"[INFO] Found FFmpeg: {matches[0]}")
                break

    return binaries


def find_libmpv() -> list:
    """查找 libmpv 共享库（python-mpv 的 ctypes 依赖）。"""
    binaries = []
    current_system = platform.system()

    if current_system == "Linux":
        patterns = [
            "/usr/lib/x86_64-linux-gnu/libmpv.so*",
            "/usr/lib64/libmpv.so*",
            "/usr/lib/libmpv.so*",
        ]
        conda_prefix = os.environ.get("CONDA_PREFIX")
        if conda_prefix:
            patterns.insert(0, os.path.join(conda_prefix, "lib", "libmpv.so*"))

        for pattern in patterns:
            matches = sorted(glob.glob(pattern))
            for match in matches:
                if (match, ".") not in binaries:
                    binaries.append((match, "."))
                    print(f"[INFO] Found libmpv: {match}")
            if matches:
                break

    elif current_system == "Darwin":
        brew_paths = [
            "/opt/homebrew/lib/libmpv.dylib",
            "/usr/local/lib/libmpv.dylib",
            "/opt/homebrew/lib/libmpv.2.dylib",
            "/usr/local/lib/libmpv.2.dylib",
        ]
        for lib_path in brew_paths:
            if os.path.exists(lib_path):
                binaries.append((lib_path, "."))
                print(f"[INFO] Found libmpv: {lib_path}")
                break

    elif current_system == "Windows":
        search_dirs = [os.path.dirname(sys.executable), str(PROJECT_ROOT)]
        search_dirs.extend(os.environ.get("PATH", "").split(os.pathsep))
        dll_names = ["mpv-2.dll", "libmpv-2.dll", "mpv.dll"]

        for search_dir in search_dirs:
            if not search_dir:
                continue
            for dll_name in dll_names:
                dll_path = os.path.join(search_dir, dll_name)
                if os.path.exists(dll_path):
                    binaries.append((dll_path, "."))
                    print(f"[INFO] Found libmpv: {dll_path}")
                    return binaries

    if not binaries:
        print("[WARN] libmpv not found! mpv backend may not work in packaged app.")

    return binaries


def find_gstreamer_plugins() -> tuple:
    """查找GStreamer插件和库（QtMultimedia在Linux上的后端）"""
    binaries = []
    datas = []

    if platform.system() != "Linux":
        return binaries, datas

    # 查找GStreamer安装路径
    gst_paths = [
        "/usr/lib/x86_64-linux-gnu/gstreamer-1.0",
        "/usr/lib/gstreamer-1.0",
        "/usr/lib64/gstreamer-1.0",
    ]

    # 也检查conda环境
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        gst_paths.insert(0, os.path.join(conda_prefix, "lib", "gstreamer-1.0"))

    gst_plugin_path = None
    for path in gst_paths:
        if os.path.exists(path):
            gst_plugin_path = path
            print(f"[INFO] Found GStreamer plugins: {path}")
            break

    if not gst_plugin_path:
        print("[WARN] GStreamer plugins not found")
        return binaries, datas

    # 必需的GStreamer插件用于音频播放
    essential_plugins = [
        # 核心插件
        "libgstcoreelements.so",
        "libgstcoretracers.so",
        # 音频处理
        "libgstaudioconvert.so",
        "libgstaudioresample.so",
        "libgstaudiorate.so",
        "libgstvolume.so",
        # 解码器
        "libgstdecodebin.so",
        "libgstdecodebin2.so",
        "libgstplayback.so",
        "libgsttypefindfunctions.so",
        # 音频格式支持
        "libgstmpg123.so",       # MP3
        "libgstflac.so",         # FLAC
        "libgstvorbis.so",       # OGG Vorbis
        "libgstogg.so",          # OGG container
        "libgstopus.so",         # Opus
        "libgstlame.so",         # MP3 encoding
        "libgstwavparse.so",     # WAV
        "libgstapetag.so",       # APE tags
        "libgstid3demux.so",     # ID3 tags
        "libgsticydemux.so",     # ICY demuxer
        "libgstisomp4.so",       # MP4/M4A
        "libgstfaad.so",         # AAC
        "libgstfaac.so",         # AAC encoding
        # ALSA/PulseAudio输出
        "libgstalsa.so",
        "libgstpulse.so",
        "libgstpulseaudio.so",
        # 自动检测
        "libgstautoconvert.so",
        "libgstautodetect.so",
        # 其他常用
        "libgstapp.so",
        "libgstpbtypes.so",
    ]

    # 收集插件
    for plugin in essential_plugins:
        plugin_path = os.path.join(gst_plugin_path, plugin)
        if os.path.exists(plugin_path):
            binaries.append((plugin_path, "gstreamer-1.0"))
            print(f"[INFO] Found GStreamer plugin: {plugin}")

    # 收集GStreamer核心库
    gst_lib_patterns = [
        "/usr/lib/x86_64-linux-gnu/libgst*-1.0.so*",
        "/usr/lib/libgst*-1.0.so*",
        "/usr/lib64/libgst*-1.0.so*",
    ]

    if conda_prefix:
        gst_lib_patterns.insert(0, os.path.join(conda_prefix, "lib", "libgst*-1.0.so*"))

    for pattern in gst_lib_patterns:
        matches = glob.glob(pattern)
        for match in matches:
            if (match, ".") not in binaries:
                binaries.append((match, "."))
                print(f"[INFO] Found GStreamer lib: {match}")

    # 收集glib/gobject库（GStreamer依赖）
    glib_patterns = [
        "/usr/lib/x86_64-linux-gnu/libglib-2.0.so*",
        "/usr/lib/x86_64-linux-gnu/libgobject-2.0.so*",
        "/usr/lib/x86_64-linux-gnu/libgio-2.0.so*",
        "/usr/lib/x86_64-linux-gnu/libgmodule-2.0.so*",
    ]

    for pattern in glib_patterns:
        matches = glob.glob(pattern)
        for match in matches:
            if (match, ".") not in binaries:
                binaries.append((match, "."))
                print(f"[INFO] Found GLib: {match}")

    return binaries, datas


def create_windows_version_file() -> Path:
    """Create Windows version file for PyInstaller."""
    version_file = PROJECT_ROOT / "version_info.txt"

    # Parse version string
    version_parts = APP_VERSION.lstrip('v').split('.')
    while len(version_parts) < 4:
        version_parts.append('0')
    major, minor, patch, build = version_parts[:4]

    content = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, {build}),
    prodvers=({major}, {minor}, {patch}, {build}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [
            StringStruct(u'CompanyName', u'{AUTHOR}'),
            StringStruct(u'FileDescription', u'{DESCRIPTION}'),
            StringStruct(u'FileVersion', u'{APP_VERSION}'),
            StringStruct(u'InternalName', u'{APP_NAME}'),
            StringStruct(u'LegalCopyright', u'Copyright 2024 {AUTHOR}'),
            StringStruct(u'OriginalFilename', u'{APP_NAME}.exe'),
            StringStruct(u'ProductName', u'{APP_NAME}'),
            StringStruct(u'ProductVersion', u'{APP_VERSION}'),
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""

    with open(version_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Created Windows version file: {version_file}")
    return version_file


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

    # Add version file for Windows
    if target_platform == "windows":
        version_file = create_windows_version_file()
        cmd.extend(["--version-file", str(version_file)])
        print(f"Using version file: {version_file}")

    # Add data files
    data_files = collect_data_files()
    for src, dst in data_files:
        cmd.extend(["--add-data", f"{src}{os.pathsep}{dst}"])
        print(f"Adding data: {src} -> {dst}")

    # Add hidden imports - 使用自动收集
    print("\nCollecting hidden imports...")
    hidden_imports = collect_hidden_imports()
    print(f"Total hidden imports: {len(hidden_imports)}")

    # Add SSL certificates
    ssl_datas = collect_ssl_certificates()
    for src, dst in ssl_datas:
        cmd.extend(["--add-data", f"{src}{os.pathsep}{dst}"])
        print(f"Adding SSL certs: {src} -> {dst}")

    # Add binaries (OpenSSL, Qt plugins, FFmpeg, GStreamer)
    print("\nCollecting binaries...")
    all_binaries = []
    all_binaries += find_openssl_libs()
    all_binaries += find_qt_plugins()
    all_binaries += find_ffmpeg_libs()
    all_binaries += find_libmpv()

    # Add GStreamer plugins (Linux only, can be disabled)
    include_gstreamer = os.environ.get("HARMONY_INCLUDE_GSTREAMER", "1") == "1"
    if include_gstreamer:
        gst_binaries, gst_datas = find_gstreamer_plugins()
        all_binaries += gst_binaries
        for src, dst in gst_datas:
            cmd.extend(["--add-data", f"{src}{os.pathsep}{dst}"])
    else:
        print("[INFO] Skip GStreamer plugins (HARMONY_INCLUDE_GSTREAMER=0)")

    print(f"Total binaries: {len(all_binaries)}")

    for src, dst in all_binaries:
        cmd.extend(["--add-binary", f"{src}{os.pathsep}{dst}"])
        print(f"Adding binary: {src} -> {dst}")

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
        print("\n[OK] Build completed successfully!")

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
        print(f"\n[ERROR] Build failed with error: {e}")
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


def create_linux_package():
    """Create Linux installation package with .desktop file and icon."""
    print("\nCreating Linux package...")

    # Copy icon to dist directory
    icon_src = PROJECT_ROOT / "icon.png"
    if icon_src.exists():
        icon_dst = DIST_DIR / "harmony.png"
        shutil.copy(icon_src, icon_dst)
        print(f"Copied icon: {icon_dst}")

    # Copy .desktop file
    desktop_src = PROJECT_ROOT / "harmony.desktop"
    if desktop_src.exists():
        desktop_dst = DIST_DIR / "harmony.desktop"
        shutil.copy(desktop_src, desktop_dst)
        print(f"Copied .desktop file: {desktop_dst}")

    # Create install script
    install_script = f"""#!/bin/bash
# Harmony Music Player - Linux Installation Script

set -e

INSTALL_DIR="/opt/{APP_NAME.lower()}"
BIN_LINK="/usr/local/bin/{APP_NAME.lower()}"
DESKTOP_FILE="/usr/share/applications/{APP_NAME.lower()}.desktop"
ICON_FILE="/usr/share/icons/hicolor/512x512/apps/{APP_NAME.lower()}.png"

echo "Installing {APP_NAME} Music Player..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./install.sh)"
    exit 1
fi

# Create installation directory
mkdir -p "$INSTALL_DIR"

# Copy executable
cp {APP_NAME} "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/{APP_NAME}"

# Copy icon
if [ -f "{APP_NAME.lower()}.png" ]; then
    mkdir -p /usr/share/icons/hicolor/512x512/apps
    cp {APP_NAME.lower()}.png "$ICON_FILE"
    gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
fi

# Install .desktop file
if [ -f "{APP_NAME.lower()}.desktop" ]; then
    # Update paths in .desktop file
    sed -e "s|Exec=.*|Exec=$INSTALL_DIR/{APP_NAME} %F|" \\
        -e "s|Icon=.*|Icon={APP_NAME.lower()}|" \\
        {APP_NAME.lower()}.desktop > "$DESKTOP_FILE"
fi

# Create symlink in PATH
ln -sf "$INSTALL_DIR/{APP_NAME}" "$BIN_LINK"

echo ""
echo "[OK] Installation complete!"
echo ""
echo "You can now run {APP_NAME} by:"
echo "  - Typing '{APP_NAME.lower()}' in terminal"
echo "  - Finding it in your application menu"
echo ""
echo "To uninstall, run: sudo ./uninstall.sh"
"""
    install_path = DIST_DIR / "install.sh"
    with open(install_path, "w") as f:
        f.write(install_script)
    os.chmod(install_path, 0o755)
    print(f"Created install script: {install_path}")

    # Create uninstall script
    uninstall_script = f"""#!/bin/bash
# Harmony Music Player - Linux Uninstallation Script

set -e

INSTALL_DIR="/opt/{APP_NAME.lower()}"
BIN_LINK="/usr/local/bin/{APP_NAME.lower()}"
DESKTOP_FILE="/usr/share/applications/{APP_NAME.lower()}.desktop"
ICON_FILE="/usr/share/icons/hicolor/512x512/apps/{APP_NAME.lower()}.png"

echo "Uninstalling {APP_NAME} Music Player..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./uninstall.sh)"
    exit 1
fi

# Remove files
rm -rf "$INSTALL_DIR"
rm -f "$BIN_LINK"
rm -f "$DESKTOP_FILE"
rm -f "$ICON_FILE"

# Update icon cache
gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true

echo "[OK] Uninstallation complete!"
"""
    uninstall_path = DIST_DIR / "uninstall.sh"
    with open(uninstall_path, "w") as f:
        f.write(uninstall_script)
    os.chmod(uninstall_path, 0o755)
    print(f"Created uninstall script: {uninstall_path}")


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
        target_platform = target or platform.system().lower()
        success = build_executable(
            platform_name=target,
            one_file=not args.dir,
            clean=args.no_clean is False,
            debug=args.debug,
        )

        if success:
            create_readme()
            # Create platform-specific packages
            if target_platform == "linux":
                create_linux_package()

    print("\nDone!")


if __name__ == "__main__":
    main()
