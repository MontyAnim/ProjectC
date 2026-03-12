"""
Unit tests for :mod:`core.config`.

Covers ``ExportJobConfig`` serialisation round-trip and edge cases
in :meth:`from_dict`.
"""

from __future__ import annotations

import pytest

from core.config import ExportJobConfig, ExportScope
from core.naming import NamingRule


class TestExportJobConfigRoundTrip:
    """to_dict / from_dict should produce identical configs."""

    def test_defaults_round_trip(self) -> None:
        """Default config survives serialisation."""
        original = ExportJobConfig()
        rebuilt = ExportJobConfig.from_dict(original.to_dict())
        assert rebuilt.to_dict() == original.to_dict()

    def test_full_config_round_trip(self) -> None:
        """A fully-populated config survives serialisation."""
        rule = NamingRule(
            prefix="SM",
            suffix="LOD0",
            separator="-",
            use_object_name=True,
            use_collection_name=True,
            counter_digits=3,
        )
        original = ExportJobConfig(
            output_dir="/exports/test",
            format="GLTF",
            naming_rule=rule,
            scope=ExportScope.COLLECTION,
            native_export_kwargs={
                "use_selection": True,
                "apply_modifiers": True,
            },
            create_subdirs=True,
        )
        rebuilt = ExportJobConfig.from_dict(original.to_dict())
        assert rebuilt.to_dict() == original.to_dict()


class TestExportJobConfigFromDict:
    """Edge-case handling in from_dict."""

    def test_empty_dict_uses_defaults(self) -> None:
        """An empty dict produces a default config."""
        config = ExportJobConfig.from_dict({})
        assert config.format == "FBX"
        assert config.scope == ExportScope.SELECTED

    def test_invalid_scope_falls_back(self) -> None:
        """An unrecognised scope string falls back to SELECTED."""
        config = ExportJobConfig.from_dict(
            {"scope": "invalid_scope"},
        )
        assert config.scope == ExportScope.SELECTED

    def test_missing_naming_rule_section(self) -> None:
        """Missing naming_rule key still creates valid rule."""
        config = ExportJobConfig.from_dict(
            {"format": "OBJ"},
        )
        assert config.naming_rule.separator == "_"
        assert config.naming_rule.use_object_name is True
