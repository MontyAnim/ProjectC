"""
Naming convention engine for BatchExporter.

Provides a configurable rule system that assembles export filenames
and output paths from contextual tokens (object name, collection name,
counters, etc.).  Designed to be DCC-agnostic so it can be shared
between the Blender extension and a future Maya plug-in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


# Characters that are unsafe in file / directory names across platforms.
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass
class NamingRule:
    """Configurable naming rule for exported files.

    Attributes:
        prefix: Optional string prepended to every filename.
        suffix: Optional string appended to every filename.
        separator: Character placed between naming tokens
            (default ``"_"``).
        use_object_name: Include the source object's name in
            the filename.
        use_collection_name: Include the parent collection name
            in the filename.
        counter_digits: Number of zero-padded digits for the
            auto-increment counter (e.g. ``3`` → ``001``).
            Set to ``0`` to disable counters.
    """

    prefix: str = ""
    suffix: str = ""
    separator: str = "_"
    use_object_name: bool = True
    use_collection_name: bool = False
    counter_digits: int = 0


def sanitize_token(token: str) -> str:
    """Remove characters that are invalid in filenames.

    Parameters:
        token: Raw string token (e.g. an object name).

    Returns:
        A sanitised copy safe for use in a filesystem path.
    """

    return _UNSAFE_CHARS.sub("", token).strip()


def resolve_name(
    rule: NamingRule,
    context: Dict[str, str],
) -> str:
    """Assemble an export filename from a naming rule and context.

    The assembled order is:
    ``prefix`` – ``collection_name`` – ``object_name`` – ``suffix``
    – ``counter``, joined by :attr:`NamingRule.separator`.

    Parameters:
        rule: The naming rule that drives assembly.
        context: A dict with optional keys ``"object_name"``,
            ``"collection_name"``, and ``"counter"`` (int as str).

    Returns:
        The resolved filename **without** a file extension.
    """

    parts: list[str] = []

    if rule.prefix:
        parts.append(sanitize_token(rule.prefix))

    if rule.use_collection_name:
        col = context.get("collection_name", "")
        if col:
            parts.append(sanitize_token(col))

    if rule.use_object_name:
        obj = context.get("object_name", "")
        if obj:
            parts.append(sanitize_token(obj))

    if rule.suffix:
        parts.append(sanitize_token(rule.suffix))

    if rule.counter_digits > 0 and "counter" in context:
        try:
            counter_val = int(context["counter"])
            fmt = f"{{:0{rule.counter_digits}d}}"
            parts.append(fmt.format(counter_val))
        except (ValueError, KeyError):
            pass

    return rule.separator.join(parts)


def resolve_output_path(
    base_dir: Path,
    rule: NamingRule,
    context: Dict[str, str],
    extension: str,
    create_subdirs: bool = False,
) -> Path:
    """Build the full output path for an export.

    Parameters:
        base_dir: Root export directory chosen by the user.
        rule: The naming rule that drives filename assembly.
        context: Contextual tokens forwarded to
            :func:`resolve_name`.
        extension: File extension **with** leading dot
            (e.g. ``".fbx"``).
        create_subdirs: When ``True``, create a subdirectory
            named after the prefix (if set) or collection name.

    Returns:
        A :class:`~pathlib.Path` pointing to the target file.
    """

    subdir = _resolve_subdir(rule, context) if create_subdirs else ""
    filename = resolve_name(rule, context) + extension
    output = base_dir / subdir / filename if subdir else base_dir / filename
    return output


def _resolve_subdir(
    rule: NamingRule,
    context: Dict[str, str],
) -> str:
    """Determine the subdirectory name for grouped exports.

    Uses the prefix when available, otherwise falls back to the
    collection name.  Returns an empty string when neither is set.
    """

    if rule.prefix:
        return sanitize_token(rule.prefix)

    col = context.get("collection_name", "")
    if col:
        return sanitize_token(col)

    return ""
