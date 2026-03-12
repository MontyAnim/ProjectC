"""
Export reporting for BatchExporter.

Collects per-file results during a batch run and produces a
human-readable summary.  DCC-agnostic — the Blender layer calls
:func:`format_report` to display results in the info area.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import List, Optional


class ExportStatus(enum.Enum):
    """Result status for a single exported file."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class ExportResult:
    """Outcome of exporting one item.

    Attributes:
        name: Source object / collection / scene name.
        path: Destination file path that was written (or
            attempted).
        status: Whether the export succeeded, was skipped,
            or failed.
        duration: Wall-clock seconds the individual export
            took.  ``None`` when not measured.
        error: Error description when *status* is
            :attr:`ExportStatus.FAILED`.
    """

    name: str
    path: str
    status: ExportStatus = ExportStatus.SUCCESS
    duration: Optional[float] = None
    error: Optional[str] = None


@dataclass
class ExportReport:
    """Aggregated report for an entire batch-export run.

    Attributes:
        results: Per-item export outcomes.
    """

    results: List[ExportResult] = field(default_factory=list)

    # -- Convenience accessors ----------------------------------------

    @property
    def succeeded(self) -> List[ExportResult]:
        """Return results that completed successfully."""
        return [
            r for r in self.results
            if r.status == ExportStatus.SUCCESS
        ]

    @property
    def failed(self) -> List[ExportResult]:
        """Return results that failed."""
        return [
            r for r in self.results
            if r.status == ExportStatus.FAILED
        ]

    @property
    def skipped(self) -> List[ExportResult]:
        """Return results that were skipped."""
        return [
            r for r in self.results
            if r.status == ExportStatus.SKIPPED
        ]

    @property
    def total_duration(self) -> float:
        """Sum of all individual durations (seconds)."""
        return sum(
            r.duration for r in self.results
            if r.duration is not None
        )


def format_report(report: ExportReport) -> str:
    """Produce a human-readable summary of a batch export.

    Parameters:
        report: The completed export report.

    Returns:
        A multi-line string suitable for display in a console
        or info editor.
    """

    total = len(report.results)
    ok = len(report.succeeded)
    fail = len(report.failed)
    skip = len(report.skipped)

    lines: list[str] = [
        "=" * 50,
        "  BatchExporter — Export Report",
        "=" * 50,
        f"  Total items : {total}",
        f"  Succeeded   : {ok}",
        f"  Failed      : {fail}",
        f"  Skipped     : {skip}",
        f"  Duration    : {report.total_duration:.2f}s",
        "-" * 50,
    ]

    # Detail lines for failures so the user can diagnose issues.
    if report.failed:
        lines.append("  FAILURES:")
        for r in report.failed:
            err = r.error or "unknown error"
            lines.append(f"    • {r.name}: {err}")
        lines.append("-" * 50)

    # Detail lines for skipped items.
    if report.skipped:
        lines.append("  SKIPPED:")
        for r in report.skipped:
            lines.append(f"    • {r.name}")
        lines.append("-" * 50)

    # Successful items listed concisely.
    if report.succeeded:
        lines.append("  EXPORTED:")
        for r in report.succeeded:
            dur = (
                f" ({r.duration:.2f}s)" if r.duration else ""
            )
            lines.append(f"    ✓ {r.path}{dur}")
        lines.append("=" * 50)

    return "\n".join(lines)
