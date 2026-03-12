"""
BatchExporter — Command-line interface.

Run batch exports from the terminal without opening the Blender
UI.  Requires a JSON config file produced by the *Save Config*
button inside the Batch Export dialog.

Usage
-----
::

    blender myfile.blend --background --python cli.py \\
        -- --config batch_export_config.json

The ``--`` separates Blender flags from script arguments.
An optional ``--output`` flag overrides the output directory
saved in the config file.

Exit codes
----------
- **0** — all items exported successfully.
- **1** — one or more items failed (partial success).
- **2** — fatal error (bad config, missing file, etc.).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

# Ensure the extension root is importable when running
# via ``blender --python cli.py``.
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from core.config import ExportJobConfig, ExportScope  # noqa: E402
from core.file_io import ensure_output_dir  # noqa: E402
from core.naming import resolve_output_path  # noqa: E402
from core.report import (  # noqa: E402
    ExportReport,
    ExportResult,
    ExportStatus,
    format_report,
)

from blender.exporter import (  # noqa: E402
    export_single,
    get_format_by_id,
    load_preset_kwargs,
    resolve_preset_path,
)
from blender.utils import (  # noqa: E402
    copy_textures_for_objects,
    export_at_origin,
    gather_exportables,
    group_lod_items,
    isolate_selection,
)


import time  # noqa: E402


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments after the ``--`` separator."""

    # Blender passes everything after ``--`` as sys.argv
    # starting from the index *after* the separator.
    separator = "--"
    if separator in sys.argv:
        argv = sys.argv[sys.argv.index(separator) + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(
        description="BatchExporter CLI",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to batch_export_config.json",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Override the output directory from the "
            "config file"
        ),
    )
    return parser.parse_args(argv)


def _run(args: argparse.Namespace) -> int:
    """Execute the batch-export job described by *args*.

    Parameters:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 = success, 1 = partial, 2 = fatal).
    """

    config_path = Path(args.config)
    if not config_path.is_file():
        print(
            f"ERROR: Config file not found: "
            f"{config_path}",
        )
        return 2

    try:
        data = json.loads(
            config_path.read_text(encoding="utf-8"),
        )
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: Cannot read config: {exc}")
        return 2

    config = ExportJobConfig.from_dict(data)

    if args.output:
        config.output_dir = args.output

    if not config.output_dir:
        print("ERROR: No output directory specified.")
        return 2

    # Resolve native preset kwargs if a Blender preset was
    # referenced in the config.
    if (
        config.export_preset
        and config.export_preset != "NONE"
    ):
        path = resolve_preset_path(
            config.format,
            config.export_preset,
        )
        if path:
            config.native_export_kwargs.update(
                load_preset_kwargs(path),
            )

    fmt = get_format_by_id(config.format)
    if fmt is None:
        print(
            f"ERROR: Format '{config.format}' is not "
            f"available.",
        )
        return 2

    scope = config.scope
    items = gather_exportables(
        scope,
        prefix_filter=config.filter_prefix,
        suffix_filter=config.filter_suffix,
    )

    if not items:
        print(
            "WARNING: Nothing to export for the "
            "selected scope.",
        )
        return 0

    if config.pack_lods:
        items = group_lod_items(items)

    # -- Export loop ---------------------------------------------------
    report = ExportReport()
    base_dir = Path(config.output_dir)
    original_scene = bpy.context.window.scene

    for idx, item in enumerate(items, start=1):
        ctx = {
            "object_name": item.name,
            "collection_name": item.collection_name,
            "counter": str(idx),
        }

        out_path = resolve_output_path(
            base_dir,
            config.naming_rule,
            ctx,
            fmt.extension,
            create_subdirs=config.create_subdirs,
        )

        t0 = time.perf_counter()
        try:
            ensure_output_dir(out_path.parent)

            target = bpy.data.scenes.get(
                item.scene_name,
            )
            if (
                target
                and bpy.context.window.scene != target
            ):
                bpy.context.window.scene = target

            with isolate_selection(item.objects), \
                 export_at_origin(
                     item.objects,
                     enabled=config.export_at_origin,
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
            print(f"  OK  {out_path.name} ({elapsed:.2f}s)")

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
            print(f"  FAIL {item.name}: {exc}")

    if bpy.context.window.scene != original_scene:
        bpy.context.window.scene = original_scene

    # -- Texture copy -------------------------------------------------
    if config.export_textures and report.succeeded:
        all_objects = []
        for item in items:
            all_objects.extend(item.objects)
        tex_count = copy_textures_for_objects(
            all_objects, base_dir,
        )
        if tex_count:
            print(f"Copied {tex_count} texture(s).")

    # -- Report -------------------------------------------------------
    summary = format_report(report)
    print()
    print(summary)

    ok = len(report.succeeded)
    fail = len(report.failed)
    print(
        f"Batch export complete: {ok} succeeded, "
        f"{fail} failed.",
    )

    return 1 if fail else 0


if __name__ == "__main__":
    code = _run(_parse_args())
    sys.exit(code)
