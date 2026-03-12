"""
File I/O helpers for BatchExporter.

Safe directory creation and output-path validation utilities used by
both the Blender extension and future DCC ports.
"""

from __future__ import annotations

import os
from pathlib import Path


def ensure_output_dir(path: Path) -> Path:
    """Create the output directory if it does not exist.

    Parameters:
        path: Target directory.  Intermediate directories are
            created as needed.

    Returns:
        The same *path* for convenient chaining.

    Raises:
        OSError: If the directory cannot be created (e.g.
            invalid drive letter or permissions error).
    """

    # Validate the drive / root anchor exists before
    # attempting to create a deep directory tree.
    anchor = path.anchor
    if anchor and not Path(anchor).exists():
        raise OSError(
            f"Cannot create output directory '{path}': "
            f"drive or root '{anchor}' does not exist"
        )

    try:
        path.mkdir(parents=True, exist_ok=True)
    except (FileNotFoundError, OSError) as exc:
        raise OSError(
            f"Cannot create output directory '{path}': "
            f"{exc}"
        ) from None
    return path


def is_writable(path: Path) -> bool:
    """Check whether *path* (or its nearest existing ancestor) is
    writable.

    Parameters:
        path: A file or directory path to test.

    Returns:
        ``True`` when the location is writable.
    """

    target = path if path.exists() else _nearest_ancestor(path)
    return os.access(target, os.W_OK)


def _nearest_ancestor(path: Path) -> Path:
    """Walk up until an existing directory is found.

    Falls back to the current working directory when no ancestor
    exists (should rarely happen).
    """

    for parent in path.parents:
        if parent.exists():
            return parent
    return Path.cwd()
