"""
BatchExporter — Blender 4.0+ Extension entry point.

Registers all operators, UI panels, menus, and preferences.
"""

from __future__ import annotations

from blender import exporter, operators, preferences, ui


def register() -> None:
    """Register all BatchExporter classes with Blender."""

    preferences.register()
    exporter.register()
    operators.register()
    ui.register()


def unregister() -> None:
    """Unregister all BatchExporter classes from Blender."""

    ui.unregister()
    operators.unregister()
    exporter.unregister()
    preferences.unregister()
