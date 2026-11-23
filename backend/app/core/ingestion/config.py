"""Centralized, framework-free ingestion limits and thresholds.

Every numeric limit used by the ingestion pipeline lives here exactly once, so no
magic number is scattered through the validator. Limits are modelled as a frozen,
dependency-injectable value object: tests can substitute their own instance
without mutating global state, and :class:`app.config.Settings` exposes the same
values as environment overrides for the application layer.

Scope discipline: only limits that M1.1 actually consumes are defined here. The
layout constants of decision D3 (spanning-block ratio, column split thresholds)
are deliberately absent - they are measured in M1.2 and applied by the parser in
M1.3, never by validation.

Threshold provenance:

- ``scanned_page_char_threshold`` / ``scanned_page_ratio`` / ``scanned_density_threshold``
  are the exact D5 document-level scanned-detection thresholds from the design.
- ``max_pdf_size_bytes`` and ``min_page_count`` are safety defaults that the design
  left unspecified; they are documented here rather than assumed silently.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

BYTES_PER_MEGABYTE: int = 1024 * 1024
"""Binary megabyte used to convert the human-facing size ceiling into bytes."""

DEFAULT_MAX_PDF_SIZE_MB: int = 50
"""Default upload ceiling: 50 MiB.

Scientific PDFs with embedded raster figures are routinely 10-30 MiB; 50 MiB
comfortably covers the benchmark corpus while still bounding the memory a single
request can demand from a CPU-only service.
"""

DEFAULT_MIN_PAGE_COUNT: int = 1
"""A valid document must contain at least one page."""


@dataclass(frozen=True, slots=True)
class IngestionLimits:
    """Immutable, injectable validation limits."""

    max_pdf_size_bytes: int = DEFAULT_MAX_PDF_SIZE_MB * BYTES_PER_MEGABYTE
    min_page_count: int = DEFAULT_MIN_PAGE_COUNT
    scanned_page_char_threshold: int = 50
    """A page is "sparse" when it yields fewer characters than this (D5)."""

    scanned_page_ratio: float = 0.80
    """A document is scanned when more than this fraction of pages are sparse (D5)."""

    scanned_density_threshold: float = 100.0
    """A document is scanned when its average characters per page is below this (D5)."""

    def __post_init__(self) -> None:
        if self.max_pdf_size_bytes <= 0:
            raise ValueError("max_pdf_size_bytes must be positive.")
        if self.min_page_count < 1:
            raise ValueError("min_page_count must be at least 1.")
        if self.scanned_page_char_threshold < 0:
            raise ValueError("scanned_page_char_threshold must not be negative.")
        if not math.isfinite(self.scanned_page_ratio):
            raise ValueError(f"scanned_page_ratio must be finite: {self.scanned_page_ratio}.")
        if not 0.0 <= self.scanned_page_ratio <= 1.0:
            raise ValueError("scanned_page_ratio must be within [0, 1].")
        if not math.isfinite(self.scanned_density_threshold):
            raise ValueError(
                f"scanned_density_threshold must be finite: {self.scanned_density_threshold}."
            )
        if self.scanned_density_threshold < 0.0:
            raise ValueError("scanned_density_threshold must not be negative.")


DEFAULT_INGESTION_LIMITS: IngestionLimits = IngestionLimits()
"""Process-wide default limits; overridden per call or via ``app.config`` settings."""
