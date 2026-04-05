from __future__ import annotations

import zipfile
from pathlib import Path


def build_plugin_zip(plugin_root: Path, output_zip: Path) -> Path:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in plugin_root.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(plugin_root))
    return output_zip
