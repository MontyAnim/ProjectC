"""
Unit tests for :mod:`core.file_io` and :mod:`core.report`.

Covers directory creation, writability checks, and export report
formatting.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.file_io import ensure_output_dir, is_writable
from core.report import (
    ExportReport,
    ExportResult,
    ExportStatus,
    format_report,
)


# -- ensure_output_dir ------------------------------------------------

class TestEnsureOutputDir:
    """Tests for :func:`ensure_output_dir`."""

    def test_creates_directory(self, tmp_path: Path) -> None:
        """Creates a nested directory that didn't exist."""
        target = tmp_path / "a" / "b" / "c"
        result = ensure_output_dir(target)
        assert target.exists()
        assert target.is_dir()
        assert result == target

    def test_existing_directory_is_fine(
        self,
        tmp_path: Path,
    ) -> None:
        """No error when directory already exists."""
        result = ensure_output_dir(tmp_path)
        assert result == tmp_path

    def test_invalid_drive_raises_os_error(
        self,
    ) -> None:
        """An invalid drive letter raises OSError."""
        with pytest.raises(OSError, match="Cannot create"):
            ensure_output_dir(Path("Z:/nonexistent/path"))


# -- is_writable ------------------------------------------------------

class TestIsWritable:
    """Tests for :func:`is_writable`."""

    def test_existing_writable_dir(self, tmp_path: Path) -> None:
        """An existing temp directory should be writable."""
        assert is_writable(tmp_path) is True

    def test_nonexistent_path_checks_ancestor(
        self,
        tmp_path: Path,
    ) -> None:
        """A non-existent path checks the nearest ancestor."""
        deep = tmp_path / "x" / "y" / "z"
        assert is_writable(deep) is True


# -- format_report ----------------------------------------------------

class TestFormatReport:
    """Tests for :func:`format_report`."""

    def test_empty_report(self) -> None:
        """An empty report renders without crashing."""
        report = ExportReport()
        text = format_report(report)
        assert "Total items : 0" in text

    def test_successful_items_listed(self) -> None:
        """Successful exports appear in the EXPORTED section."""
        report = ExportReport(
            results=[
                ExportResult(
                    name="Cube",
                    path="/out/Cube.fbx",
                    status=ExportStatus.SUCCESS,
                    duration=0.12,
                ),
            ],
        )
        text = format_report(report)
        assert "Succeeded   : 1" in text
        assert "/out/Cube.fbx" in text

    def test_failures_listed(self) -> None:
        """Failed exports show the error in the FAILURES section."""
        report = ExportReport(
            results=[
                ExportResult(
                    name="Broken",
                    path="/out/Broken.fbx",
                    status=ExportStatus.FAILED,
                    duration=0.01,
                    error="Disk full",
                ),
            ],
        )
        text = format_report(report)
        assert "Failed      : 1" in text
        assert "Disk full" in text

    def test_mixed_report(self) -> None:
        """Report with a mix of statuses renders correctly."""
        report = ExportReport(
            results=[
                ExportResult(
                    name="OK",
                    path="/out/OK.fbx",
                    status=ExportStatus.SUCCESS,
                    duration=0.5,
                ),
                ExportResult(
                    name="Bad",
                    path="/out/Bad.fbx",
                    status=ExportStatus.FAILED,
                    error="Oops",
                ),
                ExportResult(
                    name="Skip",
                    path="/out/Skip.fbx",
                    status=ExportStatus.SKIPPED,
                ),
            ],
        )
        text = format_report(report)
        assert "Total items : 3" in text
        assert "Succeeded   : 1" in text
        assert "Failed      : 1" in text
        assert "Skipped     : 1" in text

    def test_total_duration(self) -> None:
        """Total duration sums individual durations."""
        report = ExportReport(
            results=[
                ExportResult(
                    "A", "/a", ExportStatus.SUCCESS, 1.5,
                ),
                ExportResult(
                    "B", "/b", ExportStatus.SUCCESS, 2.5,
                ),
            ],
        )
        assert report.total_duration == pytest.approx(4.0)
