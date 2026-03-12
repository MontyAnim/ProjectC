"""
BatchExporter operators for Blender.

Contains the main ``BATCH_OT_export`` operator that drives the
batch-export loop, plus a helper for picking the output directory.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Set

import bpy

from .core.config import ExportJobConfig, ExportScope
from .core.file_io import ensure_output_dir
from .core.naming import NamingRule, resolve_name, resolve_output_path
from .core.report import (
    ExportReport,
    ExportResult,
    ExportStatus,
    format_report,
)

from .exporter import (
    export_single,
    get_format_by_id,
    get_supported_formats,
    load_preset_kwargs,
    resolve_preset_path,
)
from .utils import (
    ExportableItem,
    copy_textures_for_objects,
    export_at_origin,
    gather_exportables,
    group_lod_items,
    isolate_selection,
)


class BATCH_OT_export(bpy.types.Operator):
    """Batch-export objects, collections, or scenes."""

    bl_idname = "batch_exporter.export"
    bl_label = "Batch Export"
    bl_description = (
        "Export items individually based on scope and naming rules"
    )
    bl_options = {"REGISTER", "UNDO"}

    def invoke(
        self,
        context: bpy.types.Context,
        event: bpy.types.Event,
    ) -> Set[str]:
        """Show the settings popup before exporting.

        Parameters:
            context: Current Blender context.
            event: The triggering event.

        Returns:
            ``{'RUNNING_MODAL'}`` to keep the dialog open.
        """

        return context.window_manager.invoke_props_dialog(
            self, width=400,
        )

    def draw(self, context: bpy.types.Context) -> None:
        """Draw the batch-export settings inside the popup.

        Parameters:
            context: Current Blender context.
        """

        layout = self.layout
        settings = context.scene.batch_export_settings

        # -- Output (always visible) ----------------------------------
        box = layout.box()
        box.label(text="Output", icon="EXPORT")
        box.prop(settings, "output_dir", text="")
        box.prop(settings, "export_format")
        box.prop(settings, "export_preset")
        box.prop(settings, "export_scope")

        # -- Filename preview -----------------------------------------
        preview = self._build_preview(settings)
        preview_box = layout.box()
        preview_box.label(
            text="Preview:", icon="VIEWZOOM",
        )
        preview_box.label(text=preview)

        # -- Naming (collapsible) -------------------------------------
        box = layout.box()
        row = box.row()
        row.prop(
            settings, "show_naming",
            icon=(
                "TRIA_DOWN" if settings.show_naming
                else "TRIA_RIGHT"
            ),
            emboss=False,
        )
        if settings.show_naming:
            col = box.column(align=True)
            col.prop(settings, "naming_prefix")
            col.prop(settings, "naming_suffix")
            col.prop(settings, "naming_separator")
            col.separator()
            col.prop(settings, "use_object_name")
            col.prop(settings, "use_collection_name")
            col.prop(settings, "counter_digits")
            col.separator()
            col.prop(settings, "create_subdirs")

        # -- Filters (collapsible) ------------------------------------
        box = layout.box()
        row = box.row()
        row.prop(
            settings, "show_filters",
            icon=(
                "TRIA_DOWN" if settings.show_filters
                else "TRIA_RIGHT"
            ),
            emboss=False,
        )
        if settings.show_filters:
            col = box.column(align=True)
            col.prop(settings, "filter_prefix")
            col.prop(settings, "filter_suffix")

        # -- Advanced (collapsible) -----------------------------------
        box = layout.box()
        row = box.row()
        row.prop(
            settings, "show_advanced",
            icon=(
                "TRIA_DOWN" if settings.show_advanced
                else "TRIA_RIGHT"
            ),
            emboss=False,
        )
        if settings.show_advanced:
            col = box.column(align=True)
            col.prop(settings, "export_at_origin")
            col.prop(settings, "pack_lods")
            col.prop(settings, "export_textures")

        # -- Save / Load config ---------------------------------------
        row = layout.row(align=True)
        row.operator(
            "batch_exporter.save_config",
            text="Save Config",
            icon="FILE_TICK",
        )
        row.operator(
            "batch_exporter.load_config",
            text="Load Config",
            icon="FILE_FOLDER",
        )

    @staticmethod
    def _build_preview(
        settings: Any,
    ) -> str:
        """Build a live filename preview from current settings."""

        rule = NamingRule(
            prefix=settings.naming_prefix,
            suffix=settings.naming_suffix,
            separator=settings.naming_separator,
            use_object_name=settings.use_object_name,
            use_collection_name=settings.use_collection_name,
            counter_digits=settings.counter_digits,
        )
        ctx = {
            "object_name": "ObjectName",
            "collection_name": "Collection",
            "counter": "1",
        }
        name = resolve_name(rule, ctx)
        if not name:
            name = "ObjectName"

        # Resolve extension from selected format.
        ext = ".fbx"
        fmt = get_format_by_id(settings.export_format)
        if fmt is not None:
            ext = fmt.extension

        subdir = ""
        if settings.create_subdirs:
            if settings.naming_prefix:
                subdir = settings.naming_prefix + "/"
            else:
                subdir = "Collection/"

        return f"{subdir}{name}{ext}"

    def execute(
        self,
        context: bpy.types.Context,
    ) -> Set[str]:
        """Run the batch-export loop.

        Reads configuration from the scene's
        :class:`BatchExportSettings` property group, iterates
        over exportable items, and writes each to disk.

        Parameters:
            context: Current Blender context.

        Returns:
            ``{'FINISHED'}`` on success,
            ``{'CANCELLED'}`` on failure.
        """

        settings = context.scene.batch_export_settings
        config = self._build_config(settings)

        # Validate output directory.
        if not config.output_dir:
            self.report(
                {"ERROR"},
                "No output directory specified.",
            )
            return {"CANCELLED"}

        fmt = get_format_by_id(config.format)
        if fmt is None:
            self.report(
                {"ERROR"},
                f"Format '{config.format}' is not available.",
            )
            return {"CANCELLED"}

        scope = ExportScope(config.scope.value)
        items = gather_exportables(
            scope,
            prefix_filter=settings.filter_prefix,
            suffix_filter=settings.filter_suffix,
        )

        if not items:
            if scope == ExportScope.SELECTED:
                msg = "No objects selected."
            else:
                msg = (
                    "Nothing to export for the selected "
                    "scope."
                )
            self.report({"WARNING"}, msg)
            return {"CANCELLED"}

        # Optionally group LOD variants into a single file.
        if settings.pack_lods:
            items = group_lod_items(items)

        report = self._export_items(
            items, config, fmt.extension,
            export_at_origin_enabled=(
                settings.export_at_origin
            ),
        )

        # Copy textures alongside exported files.
        if settings.export_textures and report.succeeded:
            all_objects = []
            for item in items:
                all_objects.extend(item.objects)
            tex_count = copy_textures_for_objects(
                all_objects,
                Path(config.output_dir),
            )
            if tex_count:
                self.report(
                    {"INFO"},
                    f"Copied {tex_count} texture(s).",
                )

        # Display summary.
        summary = format_report(report)
        for line in summary.splitlines():
            self.report({"INFO"}, line)

        ok = len(report.succeeded)
        fail = len(report.failed)
        self.report(
            {"INFO"},
            f"Batch export complete: {ok} succeeded, "
            f"{fail} failed.",
        )
        return {"FINISHED"}

    # -- Internal helpers ---------------------------------------------

    def _build_config(
        self,
        settings: Any,
    ) -> ExportJobConfig:
        """Translate the scene property group into a core config."""

        rule = NamingRule(
            prefix=settings.naming_prefix,
            suffix=settings.naming_suffix,
            separator=settings.naming_separator,
            use_object_name=settings.use_object_name,
            use_collection_name=settings.use_collection_name,
            counter_digits=settings.counter_digits,
        )
        # Load native export kwargs from the selected
        # preset, if any.
        preset_kwargs: dict[str, Any] = {}
        if settings.export_preset != "NONE":
            path = resolve_preset_path(
                settings.export_format,
                settings.export_preset,
            )
            if path:
                preset_kwargs = load_preset_kwargs(path)

        return ExportJobConfig(
            output_dir=settings.output_dir,
            format=settings.export_format,
            naming_rule=rule,
            scope=ExportScope(settings.export_scope),
            native_export_kwargs=preset_kwargs,
            create_subdirs=settings.create_subdirs,
            filter_prefix=settings.filter_prefix,
            filter_suffix=settings.filter_suffix,
            export_preset=settings.export_preset,
            export_at_origin=settings.export_at_origin,
            pack_lods=settings.pack_lods,
            export_textures=settings.export_textures,
        )

    def _export_items(
        self,
        items: list[ExportableItem],
        config: ExportJobConfig,
        extension: str,
        export_at_origin_enabled: bool = False,
    ) -> ExportReport:
        """Iterate over *items* and export each one."""

        report = ExportReport()
        base_dir = Path(config.output_dir)
        total = len(items)

        wm = bpy.context.window_manager
        wm.progress_begin(0, total)

        # Remember the original scene so we can restore it
        # after exporting items that belong to other scenes.
        original_scene = bpy.context.window.scene

        for idx, item in enumerate(items, start=1):
            wm.progress_update(idx)

            ctx = {
                "object_name": item.name,
                "collection_name": item.collection_name,
                "counter": str(idx),
            }

            out_path = resolve_output_path(
                base_dir,
                config.naming_rule,
                ctx,
                extension,
                create_subdirs=config.create_subdirs,
            )

            t0 = time.perf_counter()
            try:
                # Ensure directories exist.
                ensure_output_dir(out_path.parent)

                # Switch scene when the item belongs to a
                # different scene (e.g. Scenes / All scope).
                target = bpy.data.scenes.get(
                    item.scene_name,
                )
                if (
                    target
                    and bpy.context.window.scene
                    != target
                ):
                    bpy.context.window.scene = target

                with isolate_selection(item.objects), \
                    export_at_origin(
                    item.objects,
                    enabled=export_at_origin_enabled,
                ):
                    export_single(
                        filepath=str(out_path),
                        format_id=config.format,
                        **config.native_export_kwargs,
                    )
                elapsed = time.perf_counter() - t0
                report.results.append(
                    ExportResult(
                        name=item.name,
                        path=str(out_path),
                        status=ExportStatus.SUCCESS,
                        duration=elapsed,
                    ),
                )
            except Exception as exc:
                elapsed = time.perf_counter() - t0
                report.results.append(
                    ExportResult(
                        name=item.name,
                        path=str(out_path),
                        status=ExportStatus.FAILED,
                        duration=elapsed,
                        error=str(exc),
                    ),
                )

        # Restore the original scene and clean up progress.
        if bpy.context.window.scene != original_scene:
            bpy.context.window.scene = original_scene
        wm.progress_end()
        return report


class BATCH_OT_pick_output_dir(bpy.types.Operator):
    """Open a file browser to pick the export output directory."""

    bl_idname = "batch_exporter.pick_output_dir"
    bl_label = "Pick Output Directory"
    bl_description = "Choose a directory for batch-exported files"
    bl_options = {"REGISTER", "INTERNAL"}

    directory: bpy.props.StringProperty(
        subtype="DIR_PATH",
    )  # type: ignore[valid-type]

    def execute(
        self,
        context: bpy.types.Context,
    ) -> Set[str]:
        """Store the chosen directory in scene settings.

        Parameters:
            context: Current Blender context.

        Returns:
            ``{'FINISHED'}``.
        """

        context.scene.batch_export_settings.output_dir = (
            self.directory
        )
        return {"FINISHED"}

    def invoke(
        self,
        context: bpy.types.Context,
        event: bpy.types.Event,
    ) -> Set[str]:
        """Open the file browser dialog.

        Parameters:
            context: Current Blender context.
            event: The triggering event.

        Returns:
            ``{'RUNNING_MODAL'}``.
        """

        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class BATCH_OT_save_config(bpy.types.Operator):
    """Save current batch-export settings to a JSON file."""

    bl_idname = "batch_exporter.save_config"
    bl_label = "Save Batch Export Config"
    bl_description = (
        "Save all current export settings to a JSON "
        "file for CLI or reuse"
    )
    bl_options = {"REGISTER"}

    filepath: bpy.props.StringProperty(
        subtype="FILE_PATH",
    )  # type: ignore[valid-type]

    filter_glob: bpy.props.StringProperty(
        default="*.json",
        options={"HIDDEN"},
    )  # type: ignore[valid-type]

    def execute(
        self,
        context: bpy.types.Context,
    ) -> Set[str]:
        """Write settings to *filepath*.

        Parameters:
            context: Current Blender context.

        Returns:
            ``{'FINISHED'}`` on success,
            ``{'CANCELLED'}`` on error.
        """

        settings = context.scene.batch_export_settings
        config = BATCH_OT_export._build_config(settings)
        data = config.to_dict()

        out = Path(self.filepath)
        if out.suffix.lower() != ".json":
            out = out.with_suffix(".json")

        try:
            out.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            self.report(
                {"ERROR"},
                f"Cannot save config: {exc}",
            )
            return {"CANCELLED"}

        self.report(
            {"INFO"},
            f"Config saved to {out}",
        )
        return {"FINISHED"}

    def invoke(
        self,
        context: bpy.types.Context,
        event: bpy.types.Event,
    ) -> Set[str]:
        """Open a file-save dialog."""

        self.filepath = "batch_export_config.json"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class BATCH_OT_load_config(bpy.types.Operator):
    """Load batch-export settings from a JSON file."""

    bl_idname = "batch_exporter.load_config"
    bl_label = "Load Batch Export Config"
    bl_description = (
        "Load export settings from a previously saved "
        "JSON config file"
    )
    bl_options = {"REGISTER", "UNDO"}

    filepath: bpy.props.StringProperty(
        subtype="FILE_PATH",
    )  # type: ignore[valid-type]

    filter_glob: bpy.props.StringProperty(
        default="*.json",
        options={"HIDDEN"},
    )  # type: ignore[valid-type]

    def execute(
        self,
        context: bpy.types.Context,
    ) -> Set[str]:
        """Read settings from *filepath* into the scene.

        Parameters:
            context: Current Blender context.

        Returns:
            ``{'FINISHED'}`` on success,
            ``{'CANCELLED'}`` on error.
        """

        path = Path(self.filepath)
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, json.JSONDecodeError) as exc:
            self.report(
                {"ERROR"},
                f"Cannot load config: {exc}",
            )
            return {"CANCELLED"}

        config = ExportJobConfig.from_dict(data)
        settings = context.scene.batch_export_settings

        settings.output_dir = config.output_dir
        settings.export_format = config.format
        settings.export_scope = config.scope.value
        settings.naming_prefix = config.naming_rule.prefix
        settings.naming_suffix = config.naming_rule.suffix
        settings.naming_separator = (
            config.naming_rule.separator
        )
        settings.use_object_name = (
            config.naming_rule.use_object_name
        )
        settings.use_collection_name = (
            config.naming_rule.use_collection_name
        )
        settings.counter_digits = (
            config.naming_rule.counter_digits
        )
        settings.create_subdirs = config.create_subdirs
        settings.filter_prefix = config.filter_prefix
        settings.filter_suffix = config.filter_suffix
        settings.export_preset = config.export_preset
        settings.export_at_origin = config.export_at_origin
        settings.pack_lods = config.pack_lods
        settings.export_textures = config.export_textures

        self.report(
            {"INFO"},
            f"Config loaded from {path.name}",
        )
        return {"FINISHED"}

    def invoke(
        self,
        context: bpy.types.Context,
        event: bpy.types.Event,
    ) -> Set[str]:
        """Open a file-open dialog."""

        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


# -- Registration -----------------------------------------------------

_classes = (
    BATCH_OT_export,
    BATCH_OT_pick_output_dir,
    BATCH_OT_save_config,
    BATCH_OT_load_config,
)


def register() -> None:
    """Register operator classes."""

    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister() -> None:
    """Unregister operator classes."""

    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
