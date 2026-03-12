# BatchExporter

A Blender 4.0+ extension that wraps Blender's native exporters to **batch-export** objects, collections, or scenes as individual files — with configurable naming conventions, filtering, and subdirectory grouping.

Built with a **shared pure-Python core** library so the same naming, config, and reporting logic can be reused in a future Maya port.

## Features

- **Multiple export scopes** — Selected objects, collections, scenes, or all mesh objects
- **All Blender-supported formats** — FBX, glTF/glb, OBJ, USD, Alembic, STL, PLY, Collada (anything `bpy.ops.export_scene.*` supports)
- **Configurable naming** — prefix, suffix, separator, object/collection name tokens, auto-increment counters
- **Subdirectory grouping** — optionally organise output by prefix or collection name
- **Name-based filtering** — restrict export to items matching a prefix/suffix pattern
- **Native exporter settings** — all transform, scale, and format-specific options pass through to Blender's built-in exporters
- **Export report** — summary of succeeded / failed / skipped items with per-file timing

## Architecture

```
ProjectC/
├── core/                  # DCC-agnostic pure Python (no bpy dependency)
│   ├── naming.py          # Naming convention engine
│   ├── config.py          # Export job configuration model
│   ├── file_io.py         # Output path & directory helpers
│   └── report.py          # Export result reporting
├── blender/               # Blender 4.0+ extension
│   ├── blender_manifest.toml
│   ├── __init__.py        # Register / unregister
│   ├── exporter.py        # Wrapper around bpy export operators
│   ├── operators.py       # BATCH_OT_export main operator
│   ├── ui.py              # Popup dialog & menu entry
│   ├── preferences.py     # Add-on preferences
│   └── utils.py           # Selection isolation, exportable gathering
├── maya/                  # (Future) Maya plug-in
└── tests/                 # Unit tests for core (pytest, no Blender needed)
```

The `core/` package has **zero DCC dependencies** — it handles naming rules, configuration serialisation, directory creation, and report formatting.  The `blender/` package provides the Blender-specific operators, UI, and native exporter integration.

## Installation

1. Download or clone this repository.
2. In Blender 4.0+, go to **Edit → Preferences → Add-ons → Install from Disk…**
3. Point to the `blender/` directory.
4. Enable the **BatchExporter** add-on.

## Usage

1. **File → Export → Batch Export…**
2. Set the output directory, format, and scope.
3. Configure naming rules (prefix, suffix, separator, etc.).
4. Optionally set prefix/suffix filters to narrow the export set.
5. Click **Export**.
6. Review the summary report in Blender's info area.

## Testing

```bash
# Core library tests (no Blender required)
python -m pytest tests/ -v
```

## Requirements

- **Blender 4.0+** (uses the new extension manifest format)
- **Python 3.11+** (ships with Blender 4.x)

## License

See [LICENSE](LICENSE) for details.
