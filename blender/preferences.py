"""
Add-on preferences for BatchExporter.

Stores user-level defaults (output directory, format, naming rule)
that persist across Blender sessions.
"""

from __future__ import annotations

from typing import Set

import bpy

from blender.exporter import get_format_items


class BatchExporterPreferences(bpy.types.AddonPreferences):
    """Persistent user preferences for BatchExporter."""

    bl_idname = "blender"

    default_output_dir: bpy.props.StringProperty(
        name="Default Output Directory",
        description="Pre-filled output path for new exports",
        subtype="DIR_PATH",
    )  # type: ignore[valid-type]

    default_format: bpy.props.EnumProperty(
        name="Default Format",
        description="Pre-selected export format",
        items=get_format_items,
    )  # type: ignore[valid-type]

    default_separator: bpy.props.StringProperty(
        name="Default Separator",
        description="Default separator between name tokens",
        default="_",
    )  # type: ignore[valid-type]

    def draw(
        self,
        context: bpy.types.Context,
    ) -> None:
        """Draw the preferences panel.

        Parameters:
            context: Current Blender context.
        """

        layout = self.layout
        layout.prop(self, "default_output_dir")
        layout.prop(self, "default_format")
        layout.prop(self, "default_separator")


# -- Registration -----------------------------------------------------

_classes = (BatchExporterPreferences,)


def register() -> None:
    """Register preference classes."""

    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister() -> None:
    """Unregister preference classes."""

    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
