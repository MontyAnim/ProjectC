"""
Blender-specific utility helpers for BatchExporter.

Selection isolation, exportable-item gathering, transform helpers,
texture copying, and LOD grouping that depend on ``bpy``.
"""

from __future__ import annotations

import contextlib
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generator, List, Optional, Sequence, Set

import bpy

from .core.config import ExportScope


@dataclass
class ExportableItem:
    """Lightweight descriptor for one thing to export.

    Attributes:
        name: Display name (object, collection, or scene).
        objects: The actual Blender objects to select when
            exporting this item.
        collection_name: Parent collection name (used by the
            naming engine).
        scene_name: Parent scene name.
    """

    name: str
    objects: List[bpy.types.Object] = field(
        default_factory=list,
    )
    collection_name: str = ""
    scene_name: str = ""


@contextlib.contextmanager
def isolate_selection(
    objects: Sequence[bpy.types.Object],
) -> Generator[None, None, None]:
    """Context manager that selects only *objects*, restoring the
    original selection on exit.

    Parameters:
        objects: The objects to select exclusively.

    Yields:
        Control back to the caller with the selection applied.
    """

    # Snapshot current state.
    prev_active = bpy.context.view_layer.objects.active
    prev_selected = [
        obj for obj in bpy.context.view_layer.objects
        if obj.select_get()
    ]

    try:
        # Deselect everything, then select only requested objects.
        bpy.ops.object.select_all(action="DESELECT")
        view_layer_objects = set(
            bpy.context.view_layer.objects,
        )
        selectable = [
            obj for obj in objects
            if obj in view_layer_objects
        ]
        for obj in selectable:
            obj.select_set(True)
        if selectable:
            bpy.context.view_layer.objects.active = (
                selectable[0]
            )
        if not selectable:
            raise RuntimeError(
                "Object '"
                + (objects[0].name if objects else "?")
                + "' can't be selected because it is "
                "not in View Layer '"
                + bpy.context.view_layer.name
                + "'!"
            )
        yield
    finally:
        # Restore previous selection.
        bpy.ops.object.select_all(action="DESELECT")
        for obj in prev_selected:
            try:
                obj.select_set(True)
            except ReferenceError:
                # Object may have been deleted during export.
                pass
        if prev_active is not None:
            try:
                bpy.context.view_layer.objects.active = (
                    prev_active
                )
            except ReferenceError:
                pass


@contextlib.contextmanager
def export_at_origin(
    objects: Sequence[bpy.types.Object],
    enabled: bool = False,
) -> Generator[None, None, None]:
    """Context manager that temporarily moves *objects* to the
    world origin for export, restoring their positions on exit.

    Parameters:
        objects: The objects to move.
        enabled: When ``False`` this is a no-op pass-through.

    Yields:
        Control back to the caller with positions applied.
    """

    if not enabled:
        yield
        return

    # Snapshot original locations (copy the Vector).
    saved: list[tuple[bpy.types.Object, Any]] = [
        (obj, obj.location.copy()) for obj in objects
    ]

    try:
        for obj, _ in saved:
            obj.location = (0.0, 0.0, 0.0)
        # Force depsgraph update so exporters see the change.
        bpy.context.view_layer.update()
        yield
    finally:
        for obj, loc in saved:
            obj.location = loc
        bpy.context.view_layer.update()


def gather_exportables(
    scope: ExportScope,
    prefix_filter: str = "",
    suffix_filter: str = "",
) -> List[ExportableItem]:
    """Collect items to export based on *scope*.

    Parameters:
        scope: Determines the iteration strategy.
        prefix_filter: When non-empty, only include items whose
            name starts with this string.
        suffix_filter: When non-empty, only include items whose
            name ends with this string.

    Returns:
        A list of :class:`ExportableItem` instances ready for
        the export loop.
    """

    items: List[ExportableItem] = []

    if scope == ExportScope.SELECTED:
        items = _gather_selected()
    elif scope == ExportScope.COLLECTION:
        items = _gather_by_collection()
    elif scope == ExportScope.SCENE:
        items = _gather_by_scene()
    elif scope == ExportScope.ALL:
        items = _gather_all()

    # Apply optional name filters.
    if prefix_filter or suffix_filter:
        items = _apply_name_filters(
            items, prefix_filter, suffix_filter,
        )

    return items


# -- Gathering strategies ---------------------------------------------

def _gather_selected() -> List[ExportableItem]:
    """Each selected object becomes its own export item."""

    items: List[ExportableItem] = []
    for obj in bpy.context.selected_objects:
        col_name = (
            obj.users_collection[0].name
            if obj.users_collection
            else ""
        )
        items.append(
            ExportableItem(
                name=obj.name,
                objects=[obj],
                collection_name=col_name,
                scene_name=bpy.context.scene.name,
            ),
        )
    return items


def _gather_by_collection() -> List[ExportableItem]:
    """Each non-empty collection becomes one export item containing
    all its direct mesh objects."""

    items: List[ExportableItem] = []
    for col in bpy.data.collections:
        meshes = [
            obj for obj in col.objects
            if obj.type == "MESH"
        ]
        if not meshes:
            continue
        items.append(
            ExportableItem(
                name=col.name,
                objects=meshes,
                collection_name=col.name,
                scene_name=bpy.context.scene.name,
            ),
        )
    return items


def _gather_by_scene() -> List[ExportableItem]:
    """Each scene becomes one export item containing all its
    mesh objects.

    The active scene is switched during export so that every
    scene's objects are reachable via the view layer.
    """

    items: List[ExportableItem] = []
    for scene in bpy.data.scenes:
        meshes = [
            obj for obj in scene.objects
            if obj.type == "MESH"
        ]
        if not meshes:
            continue
        items.append(
            ExportableItem(
                name=scene.name,
                objects=meshes,
                scene_name=scene.name,
            ),
        )
    return items


def _gather_all() -> List[ExportableItem]:
    """Every mesh object across all scenes becomes its own
    export item.

    Objects that appear in multiple scenes are only included
    once (from the first scene encountered).
    """

    items: List[ExportableItem] = []
    seen: set[str] = set()
    for scene in bpy.data.scenes:
        for obj in scene.objects:
            if obj.type != "MESH" or obj.name in seen:
                continue
            seen.add(obj.name)
            col_name = (
                obj.users_collection[0].name
                if obj.users_collection
                else ""
            )
            items.append(
                ExportableItem(
                    name=obj.name,
                    objects=[obj],
                    collection_name=col_name,
                    scene_name=scene.name,
                ),
            )
    return items


def _apply_name_filters(
    items: List[ExportableItem],
    prefix: str,
    suffix: str,
) -> List[ExportableItem]:
    """Filter *items* by optional prefix and/or suffix."""

    filtered: List[ExportableItem] = []
    for item in items:
        if prefix and not item.name.startswith(prefix):
            continue
        if suffix and not item.name.endswith(suffix):
            continue
        filtered.append(item)
    return filtered


# Pattern that matches common LOD suffixes like _LOD0, _LOD1, _lod2.
_LOD_PATTERN = re.compile(
    r"(.+?)(?:[_\-]?[Ll][Oo][Dd]\d+)$",
)


def group_lod_items(
    items: List[ExportableItem],
) -> List[ExportableItem]:
    """Group LOD variants into a single export item.

    Objects whose names match the pattern
    ``<base>_LOD0``, ``<base>_LOD1``, etc. are merged into one
    item named ``<base>`` containing all LOD meshes.

    Parameters:
        items: Ungrouped export items (one object each).

    Returns:
        A list with LOD siblings combined into single items.
        Non-LOD items are returned unchanged.
    """

    groups: dict[str, ExportableItem] = {}
    ordered_keys: list[str] = []

    for item in items:
        match = _LOD_PATTERN.match(item.name)
        if match:
            base = match.group(1)
        else:
            base = item.name

        if base in groups:
            groups[base].objects.extend(item.objects)
        else:
            groups[base] = ExportableItem(
                name=base,
                objects=list(item.objects),
                collection_name=item.collection_name,
                scene_name=item.scene_name,
            )
            ordered_keys.append(base)

    return [groups[k] for k in ordered_keys]


def copy_textures_for_objects(
    objects: Sequence[bpy.types.Object],
    output_dir: Path,
) -> int:
    """Copy textures used by *objects* into per-material folders.

    Each material gets a subfolder inside *output_dir*/textures/.
    Textures that have already been copied are skipped to avoid
    duplicates (e.g. shared atlas textures).

    Parameters:
        objects: Blender objects whose materials to scan.
        output_dir: Root export directory (textures go into
            ``output_dir / "textures" / <material_name>``).

    Returns:
        The number of texture files actually copied.
    """

    textures_root = output_dir / "textures"
    copied_paths: Set[str] = set()
    count = 0

    for obj in objects:
        if not hasattr(obj, "data") or obj.data is None:
            continue
        for slot in obj.material_slots:
            mat = slot.material
            if mat is None or not mat.use_nodes:
                continue
            mat_dir = textures_root / mat.name
            for node in mat.node_tree.nodes:
                if node.type != "TEX_IMAGE":
                    continue
                img = node.image
                if img is None or img.packed_file is not None:
                    continue
                src = bpy.path.abspath(img.filepath)
                if not src or src in copied_paths:
                    continue
                src_path = Path(src)
                if not src_path.is_file():
                    continue
                mat_dir.mkdir(parents=True, exist_ok=True)
                dst = mat_dir / src_path.name
                shutil.copy2(str(src_path), str(dst))
                copied_paths.add(src)
                count += 1

    return count
