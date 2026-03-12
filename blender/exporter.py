"""
Native exporter wrapper for BatchExporter.

Provides a thin abstraction over Blender's ``bpy.ops.export_scene.*``
operators.  All native export settings (transforms, scale, etc.) are
passed through directly — we never re-implement what Blender already
does.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import bpy


@dataclass
class FormatInfo:
    """Metadata for a supported export format.

    Attributes:
        id: Short upper-case identifier (e.g. ``"FBX"``).
        label: Human-readable label shown in the UI.
        extension: File extension **with** leading dot
            (e.g. ``".fbx"``).
        operator: Full ``bpy.ops`` path to the export operator
            (e.g. ``"export_scene.fbx"``).
    """

    id: str
    label: str
    extension: str
    operator: str


# Curated list of formats that ship with Blender by default.
# Additional formats contributed by add-ons are discovered at
# runtime via :func:`get_supported_formats`.
_BUILTIN_FORMATS: List[FormatInfo] = [
    FormatInfo("FBX", "FBX (.fbx)", ".fbx",
               "export_scene.fbx"),
    FormatInfo("GLTF", "glTF (.glb/.gltf)", ".glb",
               "export_scene.gltf"),
    FormatInfo("OBJ", "Wavefront OBJ (.obj)", ".obj",
               "wm.obj_export"),
    FormatInfo("USD", "Universal Scene Description (.usd)",
               ".usdc", "export_scene.usd"),
    FormatInfo("ABC", "Alembic (.abc)", ".abc",
               "export_scene.abc"),
    FormatInfo("STL", "STL (.stl)", ".stl",
               "export_mesh.stl"),
    FormatInfo("PLY", "Stanford PLY (.ply)", ".ply",
               "export_mesh.ply"),
    FormatInfo("DAE", "Collada (.dae)", ".dae",
               "export_scene.dae"),
]

# Module-level cache populated on first call.
_format_cache: List[FormatInfo] | None = None


def get_supported_formats(
    force_refresh: bool = False,
) -> List[FormatInfo]:
    """Return all export formats currently available in Blender.

    Results are cached after the first call for performance.
    Pass *force_refresh=True* to rebuild the list (e.g. after
    enabling / disabling add-ons).

    Returns:
        A list of :class:`FormatInfo` instances for every
        reachable export operator.
    """

    global _format_cache  # noqa: PLW0603

    if _format_cache is not None and not force_refresh:
        return list(_format_cache)

    available: List[FormatInfo] = []
    for fmt in _BUILTIN_FORMATS:
        if _operator_exists(fmt.operator):
            available.append(fmt)

    _format_cache = available
    return list(_format_cache)


def get_format_items(
    self: Any,
    context: Any,
) -> list[tuple[str, str, str]]:
    """EnumProperty callback that returns format items for UI.

    Parameters:
        self: The Blender property group or operator.
        context: The current Blender context.

    Returns:
        A list of ``(identifier, name, description)`` tuples.
    """

    return [
        (fmt.id, fmt.label, "")
        for fmt in get_supported_formats()
    ]


def get_format_by_id(format_id: str) -> FormatInfo | None:
    """Look up a format by its short identifier.

    Parameters:
        format_id: Upper-case format id (e.g. ``"FBX"``).

    Returns:
        The matching :class:`FormatInfo`, or ``None``.
    """

    for fmt in get_supported_formats():
        if fmt.id == format_id:
            return fmt
    return None


def export_single(
    filepath: str,
    format_id: str,
    **native_kwargs: Any,
) -> None:
    """Export the current selection using a native Blender operator.

    Parameters:
        filepath: Full destination path including extension.
        format_id: Upper-case format id (e.g. ``"FBX"``).
        **native_kwargs: Keyword arguments forwarded verbatim
            to the Blender export operator (e.g.
            ``use_selection=True``).

    Raises:
        ValueError: If *format_id* is not available.
        RuntimeError: If the underlying operator reports an
            error.
    """

    fmt = get_format_by_id(format_id)
    if fmt is None:
        raise ValueError(
            f"Export format '{format_id}' is not available."
        )

    op_func = _resolve_operator(fmt.operator)

    # OBJ and PLY exporters in Blender 4.0+ use a different
    # keyword for the output path.
    if fmt.id in {"OBJ", "PLY"}:
        result = op_func(
            filepath=filepath,
            export_selected_objects=True,
            **native_kwargs,
        )
    else:
        result = op_func(
            filepath=filepath,
            use_selection=True,
            **native_kwargs,
        )

    if result != {"FINISHED"}:
        raise RuntimeError(
            f"Exporter '{fmt.operator}' did not finish "
            f"successfully (result: {result})."
        )


# -- Internal helpers -------------------------------------------------

def _operator_exists(idname: str) -> bool:
    """Check whether a ``bpy.ops`` operator is registered.

    Parameters:
        idname: Dot-separated operator id
            (e.g. ``"export_scene.fbx"``).
    """

    category, name = idname.split(".", 1)
    return hasattr(getattr(bpy.ops, category, None), name)


def _resolve_operator(idname: str) -> Any:
    """Return the callable for a ``bpy.ops`` operator id.

    Parameters:
        idname: Dot-separated operator id.

    Returns:
        The callable operator function.
    """

    category, name = idname.split(".", 1)
    return getattr(getattr(bpy.ops, category), name)


# -- Registration (currently a no-op) ---------------------------------

def register() -> None:
    """Register exporter-related classes (currently none)."""


def unregister() -> None:
    """Unregister exporter-related classes (currently none)."""
