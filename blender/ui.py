"""
UI components for BatchExporter.

Popup dialog accessible from **File → Export → Batch Export…** that
lets users configure scope, naming, format, and native export settings
before running the batch.
"""

from __future__ import annotations

from typing import Any, Set

import bpy

from .exporter import get_format_items, get_preset_items
from .core.config import ExportScope


class BatchExportSettings(bpy.types.PropertyGroup):
    """Scene-level property group holding all batch-export settings.

    Registered on :attr:`bpy.types.Scene.batch_export_settings`.
    """

    output_dir: bpy.props.StringProperty(
        name="Output Directory",
        description="Root directory for exported files",
        subtype="DIR_PATH",
    )  # type: ignore[valid-type]

    export_format: bpy.props.EnumProperty(
        name="Format",
        description="Target file format",
        items=get_format_items,
    )  # type: ignore[valid-type]

    export_preset: bpy.props.EnumProperty(
        name="Preset",
        description=(
            "Native export preset for the selected "
            "format (e.g. FBX axis, scale, mesh options)"
        ),
        items=get_preset_items,
    )  # type: ignore[valid-type]

    export_scope: bpy.props.EnumProperty(
        name="Scope",
        description="What to iterate over during export",
        items=[
            (
                ExportScope.SELECTED.value,
                "Selected Objects",
                "Export each selected object individually",
            ),
            (
                ExportScope.COLLECTION.value,
                "Collections",
                "Export each collection as a separate file",
            ),
            (
                ExportScope.SCENE.value,
                "Scenes",
                "Export each scene as a separate file",
            ),
            (
                ExportScope.ALL.value,
                "All Objects",
                "Export every mesh object across all "
                "scenes individually",
            ),
        ],
    )  # type: ignore[valid-type]

    # -- Naming rule properties ---------------------------------------

    naming_prefix: bpy.props.StringProperty(
        name="Prefix",
        description="String prepended to every filename",
    )  # type: ignore[valid-type]

    naming_suffix: bpy.props.StringProperty(
        name="Suffix",
        description="String appended to every filename",
    )  # type: ignore[valid-type]

    naming_separator: bpy.props.StringProperty(
        name="Separator",
        description="Character between naming tokens",
        default="_",
    )  # type: ignore[valid-type]

    use_object_name: bpy.props.BoolProperty(
        name="Use Object Name",
        description="Include the object name in the filename",
        default=True,
    )  # type: ignore[valid-type]

    use_collection_name: bpy.props.BoolProperty(
        name="Use Collection Name",
        description=(
            "Include the collection name in the filename"
        ),
        default=False,
    )  # type: ignore[valid-type]

    counter_digits: bpy.props.IntProperty(
        name="Counter Digits",
        description=(
            "Number of zero-padded digits for the counter "
            "(e.g. 3 → 001). Set to 0 to disable"
        ),
        default=0,
        min=0,
        max=6,
    )  # type: ignore[valid-type]

    create_subdirs: bpy.props.BoolProperty(
        name="Create Subdirectories",
        description=(
            "Group exported files into subdirectories "
            "by prefix or collection name"
        ),
        default=False,
    )  # type: ignore[valid-type]

    # -- Optional name filters ----------------------------------------

    filter_prefix: bpy.props.StringProperty(
        name="Filter Prefix",
        description=(
            "Only export items whose name starts with "
            "this string (leave empty for all)"
        ),
    )  # type: ignore[valid-type]

    filter_suffix: bpy.props.StringProperty(
        name="Filter Suffix",
        description=(
            "Only export items whose name ends with "
            "this string (leave empty for all)"
        ),
    )  # type: ignore[valid-type]

    # -- Collapsible section toggles ----------------------------------

    show_naming: bpy.props.BoolProperty(
        name="Naming",
        default=False,
    )  # type: ignore[valid-type]

    show_filters: bpy.props.BoolProperty(
        name="Filters",
        default=False,
    )  # type: ignore[valid-type]

    show_advanced: bpy.props.BoolProperty(
        name="Advanced",
        default=False,
    )  # type: ignore[valid-type]

    # -- Advanced options ---------------------------------------------

    export_at_origin: bpy.props.BoolProperty(
        name="Export at Origin",
        description=(
            "Temporarily move objects to world origin "
            "(0, 0, 0) during export. Original positions "
            "are restored afterwards"
        ),
        default=False,
    )  # type: ignore[valid-type]

    pack_lods: bpy.props.BoolProperty(
        name="Pack LODs",
        description=(
            "Group LOD variants (e.g. Cube_LOD0, Cube_LOD1) "
            "into a single export file"
        ),
        default=False,
    )  # type: ignore[valid-type]

    export_textures: bpy.props.BoolProperty(
        name="Export Textures",
        description=(
            "Copy textures used by exported objects into "
            "a subfolder per material, skipping duplicates"
        ),
        default=False,
    )  # type: ignore[valid-type]


def menu_draw(
    self: Any,
    context: bpy.types.Context,
) -> None:
    """Append the Batch Export entry to the File → Export menu.

    Parameters:
        self: The menu being drawn.
        context: Current Blender context.
    """

    self.layout.separator()
    self.layout.operator(
        "batch_exporter.export",
        text="Batch Export…",
        icon="EXPORT",
    )


# -- Registration -----------------------------------------------------

_classes = (
    BatchExportSettings,
)


def register() -> None:
    """Register UI classes and menu entries."""

    for cls in _classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.batch_export_settings = (
        bpy.props.PointerProperty(type=BatchExportSettings)
    )
    bpy.types.TOPBAR_MT_file_export.append(menu_draw)


def unregister() -> None:
    """Unregister UI classes and menu entries."""

    bpy.types.TOPBAR_MT_file_export.remove(menu_draw)
    del bpy.types.Scene.batch_export_settings

    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
