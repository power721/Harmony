# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/home/harold/workspace/music-player/main.py'],
    pathex=[],
    binaries=[],
    datas=[('/home/harold/workspace/music-player/translations', 'translations')],
    hiddenimports=['PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'PySide6.QtMultimedia', 'PySide6.QtNetwork', 'PySide6.QtSvg', 'mutagen', 'mutagen.easyid3', 'mutagen.id3', 'mutagen.flac', 'mutagen.ogg', 'mutagen.oggflac', 'mutagen.oggopus', 'mutagen.oggvorbis', 'mutagen.mp4', 'mutagen.asf', 'mutagen.apev2', 'mutagen.musepack', 'mutagen.optimfrog', 'mutagen.trueaudio', 'mutagen.wavpack', 'mutagen.dsf', 'mutagen.dsd', 'mutagen.smf', 'mutagen.aac', 'mutagen.ac3', 'mutagen.aiff', 'mutagen.monkeysaudio', 'mutagen.musepack', 'mutagen.oggflac', 'mutagen.oggopus', 'mutagen.oggvorbis', 'mutagen.optimfrog', 'mutagen.trueaudio', 'mutagen.wavpack', 'requests', 'bs4', 'lxml', 'lxml.etree', 'lxml._elementpath', 'PIL', 'PIL._imaging', 'qrcode', 'qrcode.util', 'qrcode.image.pil', 'qrcode.image.svg', 'pymediainfo'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'pytest', 'sphinx', 'docutils', 'IPython', 'jupyter', 'notebook', 'torch', 'tensorflow', 'keras', 'cv2', 'opencv', 'PyQt5', 'PyQt6', 'PyQt4', 'PySide2', 'PySide', 'wx', 'gtk', 'PyObjCTools', 'objc', 'Foundation', 'AppKit', 'CoreFoundation', 'Quartz'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Harmony',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
