"""
Unit tests for :mod:`core.naming`.

Covers ``NamingRule`` defaults, ``resolve_name`` with various token
combinations, ``sanitize_token``, and ``resolve_output_path`` with
and without subdirectory creation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.naming import (
    NamingRule,
    resolve_name,
    resolve_output_path,
    sanitize_token,
)


# -- sanitize_token ---------------------------------------------------

class TestSanitizeToken:
    """Tests for :func:`sanitize_token`."""

    def test_clean_string_unchanged(self) -> None:
        """Clean names pass through unmodified."""
        assert sanitize_token("MyObject") == "MyObject"

    def test_removes_illegal_chars(self) -> None:
        """Characters illegal on Windows are stripped."""
        assert sanitize_token('My<Ob>ject:"test"') == "MyObjecttest"

    def test_strips_whitespace(self) -> None:
        """Leading/trailing whitespace is removed."""
        assert sanitize_token("  padded  ") == "padded"

    def test_empty_string(self) -> None:
        """Empty input returns empty output."""
        assert sanitize_token("") == ""


# -- resolve_name -----------------------------------------------------

class TestResolveName:
    """Tests for :func:`resolve_name`."""

    def test_object_name_only(self) -> None:
        """Default rule uses just the object name."""
        rule = NamingRule()
        ctx = {"object_name": "Cube"}
        assert resolve_name(rule, ctx) == "Cube"

    def test_prefix_and_suffix(self) -> None:
        """Prefix and suffix are added around the object name."""
        rule = NamingRule(prefix="SM", suffix="LOD0")
        ctx = {"object_name": "Cube"}
        assert resolve_name(rule, ctx) == "SM_Cube_LOD0"

    def test_collection_name_included(self) -> None:
        """Collection name appears between prefix and object name."""
        rule = NamingRule(
            prefix="SM",
            use_collection_name=True,
        )
        ctx = {
            "object_name": "Cube",
            "collection_name": "Props",
        }
        assert resolve_name(rule, ctx) == "SM_Props_Cube"

    def test_custom_separator(self) -> None:
        """Custom separator replaces the default underscore."""
        rule = NamingRule(prefix="SM", separator="-")
        ctx = {"object_name": "Cube"}
        assert resolve_name(rule, ctx) == "SM-Cube"

    def test_counter_digits(self) -> None:
        """Counter is appended when digits > 0."""
        rule = NamingRule(counter_digits=3)
        ctx = {"object_name": "Cube", "counter": "1"}
        assert resolve_name(rule, ctx) == "Cube_001"

    def test_counter_ignored_when_zero_digits(self) -> None:
        """No counter token when digits is 0."""
        rule = NamingRule(counter_digits=0)
        ctx = {"object_name": "Cube", "counter": "1"}
        assert resolve_name(rule, ctx) == "Cube"

    def test_empty_context(self) -> None:
        """With no context tokens, only prefix/suffix remain."""
        rule = NamingRule(prefix="SM", suffix="v1")
        ctx: dict[str, str] = {}
        assert resolve_name(rule, ctx) == "SM_v1"

    def test_no_tokens_at_all(self) -> None:
        """Completely empty rule + context yields empty string."""
        rule = NamingRule(use_object_name=False)
        ctx: dict[str, str] = {}
        assert resolve_name(rule, ctx) == ""

    def test_special_chars_sanitized(self) -> None:
        """Illegal filename chars in tokens are stripped."""
        rule = NamingRule()
        ctx = {"object_name": "My:Object"}
        assert resolve_name(rule, ctx) == "MyObject"


# -- resolve_output_path ----------------------------------------------

class TestResolveOutputPath:
    """Tests for :func:`resolve_output_path`."""

    def test_basic_path(self) -> None:
        """Basic path without subdirs."""
        rule = NamingRule()
        ctx = {"object_name": "Cube"}
        result = resolve_output_path(
            Path("/exports"), rule, ctx, ".fbx",
        )
        assert result == Path("/exports/Cube.fbx")

    def test_with_subdirs_by_prefix(self) -> None:
        """Subdirectory is created from prefix when enabled."""
        rule = NamingRule(prefix="SM")
        ctx = {"object_name": "Cube"}
        result = resolve_output_path(
            Path("/exports"), rule, ctx, ".fbx",
            create_subdirs=True,
        )
        assert result == Path("/exports/SM/SM_Cube.fbx")

    def test_with_subdirs_by_collection(self) -> None:
        """Falls back to collection name for subdirectory."""
        rule = NamingRule(use_collection_name=True)
        ctx = {
            "object_name": "Cube",
            "collection_name": "Props",
        }
        result = resolve_output_path(
            Path("/exports"), rule, ctx, ".glb",
            create_subdirs=True,
        )
        assert result == Path("/exports/Props/Props_Cube.glb")

    def test_no_subdirs(self) -> None:
        """Subdirectory flag off keeps flat structure."""
        rule = NamingRule(prefix="SM")
        ctx = {"object_name": "Cube"}
        result = resolve_output_path(
            Path("/exports"), rule, ctx, ".fbx",
            create_subdirs=False,
        )
        assert result == Path("/exports/SM_Cube.fbx")
