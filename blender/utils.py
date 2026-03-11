"""
Blender-specific utility helpers for BatchExporter.

Selection isolation, exportable-item gathering, and transform helpers
that depend on ``bpy``.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Generator, List, Optional, Sequence

import bpy

from core.config import ExportScope


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
        for obj in objects:
            obj.select_set(True)
        if objects:
            bpy.context.view_layer.objects.active = objects[0]
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
    """Each scene becomes one export item containing all its mesh
    objects."""

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
    """Every mesh object in the file becomes its own export item."""

    items: List[ExportableItem] = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
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
