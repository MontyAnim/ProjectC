"""
Build the Batch Exporter Blender extension package.

Assembles a distributable ``.zip`` that follows the Blender
extension format:

.. code-block:: text

    batch_exporter-1.0.0.zip
    ├── __init__.py
    ├── blender_manifest.toml
    ├── exporter.py
    ├── operators.py
    ├── preferences.py
    ├── ui.py
    ├── utils.py
    └── core/
        ├── __init__.py
        ├── config.py
        ├── file_io.py
        ├── naming.py
        └── report.py

Usage::

    python build_extension.py

Alternatively, use Blender's built-in command after this
script prepares the build directory::

    blender --command extension build \\
        --source-dir build/extension \\
        --output-dir dist
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


_ROOT = Path(__file__).resolve().parent
_BLENDER_DIR = _ROOT / "blender"
_CORE_DIR = _ROOT / "core"
_BUILD_DIR = _ROOT / "build" / "extension"
_DIST_DIR = _ROOT / "dist"

# Files to copy from blender/ into the extension root.
_EXTENSION_FILES = [
    "__init__.py",
    "blender_manifest.toml",
    "exporter.py",
    "operators.py",
    "preferences.py",
    "ui.py",
    "utils.py",
]

# Pure-Python core modules to bundle as a sub-package.
_CORE_FILES = [
    "__init__.py",
    "config.py",
    "file_io.py",
    "naming.py",
    "report.py",
]


def _read_manifest_field(
    manifest: Path,
    key: str,
) -> str:
    """Read a simple ``key = "value"`` field from the TOML manifest.

    Parameters:
        manifest: Path to ``blender_manifest.toml``.
        key: The TOML key to look up.

    Returns:
        The string value of the field.
    """

    for line in manifest.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{key} "):
            # key = "value"
            return stripped.split("=", 1)[1].strip().strip('"')
    msg = f"Key '{key}' not found in {manifest}"
    raise KeyError(msg)


def build() -> Path:
    """Assemble the extension directory and create the zip.

    Returns:
        Path to the built ``.zip`` file.
    """

    # -- Clean previous build -----------------------------------------
    if _BUILD_DIR.exists():
        shutil.rmtree(_BUILD_DIR)
    _BUILD_DIR.mkdir(parents=True)
    _DIST_DIR.mkdir(exist_ok=True)

    # -- Copy extension files -----------------------------------------
    for name in _EXTENSION_FILES:
        src = _BLENDER_DIR / name
        shutil.copy2(src, _BUILD_DIR / name)

    # -- Copy core sub-package ----------------------------------------
    core_dest = _BUILD_DIR / "core"
    core_dest.mkdir()
    for name in _CORE_FILES:
        src = _CORE_DIR / name
        shutil.copy2(src, core_dest / name)

    # -- Build zip ----------------------------------------------------
    manifest = _BUILD_DIR / "blender_manifest.toml"
    ext_id = _read_manifest_field(manifest, "id")
    ext_ver = _read_manifest_field(manifest, "version")
    zip_name = f"{ext_id}-{ext_ver}.zip"
    zip_path = _DIST_DIR / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(_BUILD_DIR.rglob("*")):
            if file.is_file() and "__pycache__" not in file.parts:
                arcname = file.relative_to(_BUILD_DIR)
                zf.write(file, arcname)

    print(f"Built extension: {zip_path}")
    print(f"  id      : {ext_id}")
    print(f"  version : {ext_ver}")
    print(
        f"\nTo validate:  "
        f"blender --command extension validate {zip_path}",
    )
    print(
        f"To install:   "
        f"Edit > Preferences > Extensions > "
        f"Install from Disk > {zip_path}",
    )
    return zip_path


if __name__ == "__main__":
    build()
