"""
Export job configuration for BatchExporter.

Defines the data model that fully describes a batch-export job:
output directory, file format, naming rules, scope, and pass-through
settings for the DCC's native exporter.  Serialisable to / from plain
dicts for JSON persistence.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict

from core.naming import NamingRule


class ExportScope(enum.Enum):
    """Determines *what* gets exported in a batch job."""

    SELECTED = "selected"
    COLLECTION = "collection"
    SCENE = "scene"
    ALL = "all"


@dataclass
class ExportJobConfig:
    """Complete configuration for a single batch-export run.

    Attributes:
        output_dir: Absolute path to the root output directory.
        format: File-format identifier recognised by the DCC
            exporter (e.g. ``"FBX"``, ``"GLTF"``).
        naming_rule: Naming convention applied to each file.
        scope: Which objects/groups to iterate over.
        native_export_kwargs: Keyword arguments passed straight
            through to the DCC's native export command so users
            keep full control over transforms, scale, etc.
        create_subdirs: Create subdirectories per prefix or
            collection name.
    """

    output_dir: str = ""
    format: str = "FBX"
    naming_rule: NamingRule = field(default_factory=NamingRule)
    scope: ExportScope = ExportScope.SELECTED
    native_export_kwargs: Dict[str, Any] = field(
        default_factory=dict,
    )
    create_subdirs: bool = False
    filter_prefix: str = ""
    filter_suffix: str = ""
    export_preset: str = "NONE"
    export_at_origin: bool = False
    pack_lods: bool = False
    export_textures: bool = False

    # -- Serialisation helpers ----------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the config to a plain dict (JSON-safe).

        Returns:
            A dictionary representation of this configuration.
        """

        return {
            "output_dir": self.output_dir,
            "format": self.format,
            "naming_rule": {
                "prefix": self.naming_rule.prefix,
                "suffix": self.naming_rule.suffix,
                "separator": self.naming_rule.separator,
                "use_object_name": self.naming_rule.use_object_name,
                "use_collection_name": (
                    self.naming_rule.use_collection_name
                ),
                "counter_digits": self.naming_rule.counter_digits,
            },
            "scope": self.scope.value,
            "native_export_kwargs": self.native_export_kwargs,
            "create_subdirs": self.create_subdirs,
            "filter_prefix": self.filter_prefix,
            "filter_suffix": self.filter_suffix,
            "export_preset": self.export_preset,
            "export_at_origin": self.export_at_origin,
            "pack_lods": self.pack_lods,
            "export_textures": self.export_textures,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExportJobConfig:
        """Deserialise a config from a plain dict.

        Parameters:
            data: Dictionary previously produced by
                :meth:`to_dict`.

        Returns:
            A reconstructed :class:`ExportJobConfig` instance.
        """

        nr_data = data.get("naming_rule", {})
        naming_rule = NamingRule(
            prefix=nr_data.get("prefix", ""),
            suffix=nr_data.get("suffix", ""),
            separator=nr_data.get("separator", "_"),
            use_object_name=nr_data.get("use_object_name", True),
            use_collection_name=nr_data.get(
                "use_collection_name", False,
            ),
            counter_digits=nr_data.get("counter_digits", 0),
        )

        scope_str = data.get("scope", "selected")
        try:
            scope = ExportScope(scope_str)
        except ValueError:
            scope = ExportScope.SELECTED

        return cls(
            output_dir=data.get("output_dir", ""),
            format=data.get("format", "FBX"),
            naming_rule=naming_rule,
            scope=scope,
            native_export_kwargs=data.get(
                "native_export_kwargs", {},
            ),
            create_subdirs=data.get("create_subdirs", False),
            filter_prefix=data.get("filter_prefix", ""),
            filter_suffix=data.get("filter_suffix", ""),
            export_preset=data.get("export_preset", "NONE"),
            export_at_origin=data.get(
                "export_at_origin", False,
            ),
            pack_lods=data.get("pack_lods", False),
            export_textures=data.get(
                "export_textures", False,
            ),
        )
