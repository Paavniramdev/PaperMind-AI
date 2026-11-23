"""Tests for centralized ingestion limits and their configuration wiring."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.config import Settings
from app.core.ingestion.config import (
    BYTES_PER_MEGABYTE,
    DEFAULT_INGESTION_LIMITS,
    DEFAULT_MAX_PDF_SIZE_MB,
    DEFAULT_MIN_PAGE_COUNT,
    IngestionLimits,
)

NON_FINITE_FLOATS: tuple[float, ...] = (float("nan"), float("inf"), float("-inf"))
NON_FINITE_FLOAT_IDS: tuple[str, ...] = ("nan", "inf", "-inf")

FLOAT_LIMIT_FIELDS: tuple[str, ...] = ("scanned_page_ratio", "scanned_density_threshold")
"""The float-typed limits, i.e. the ones for which "finite" is meaningful."""


def load_settings() -> Settings:
    """Instantiate settings while ignoring any developer ``.env`` file."""
    return Settings(_env_file=None)


class TestDefaultLimits:
    """The D5 thresholds and documented safety defaults."""

    def test_d5_scanned_thresholds_are_exact(self) -> None:
        assert DEFAULT_INGESTION_LIMITS.scanned_page_char_threshold == 50
        assert DEFAULT_INGESTION_LIMITS.scanned_page_ratio == 0.80
        assert DEFAULT_INGESTION_LIMITS.scanned_density_threshold == 100.0

    def test_size_ceiling_default_is_documented_value(self) -> None:
        assert DEFAULT_MAX_PDF_SIZE_MB == 50
        assert (
            DEFAULT_INGESTION_LIMITS.max_pdf_size_bytes
            == DEFAULT_MAX_PDF_SIZE_MB * BYTES_PER_MEGABYTE
        )

    def test_minimum_page_count_default_is_one(self) -> None:
        assert DEFAULT_MIN_PAGE_COUNT == 1
        assert DEFAULT_INGESTION_LIMITS.min_page_count == 1

    def test_default_limits_are_immutable(self) -> None:
        with pytest.raises(FrozenInstanceError):
            DEFAULT_INGESTION_LIMITS.max_pdf_size_bytes = 1  # type: ignore[misc]

    def test_limits_expose_no_layout_constants(self) -> None:
        """D3 layout constants belong to the parser, never to validation."""
        field_names = {field for field in IngestionLimits.__dataclass_fields__}

        assert field_names == {
            "max_pdf_size_bytes",
            "min_page_count",
            "scanned_page_char_threshold",
            "scanned_page_ratio",
            "scanned_density_threshold",
        }


class TestLimitValidation:
    """Limits reject nonsensical configuration eagerly."""

    @pytest.mark.parametrize(
        "overrides",
        [
            {"max_pdf_size_bytes": 0},
            {"max_pdf_size_bytes": -1},
            {"min_page_count": 0},
            {"scanned_page_char_threshold": -1},
            {"scanned_page_ratio": -0.01},
            {"scanned_page_ratio": 1.01},
            {"scanned_density_threshold": -1.0},
        ],
    )
    def test_invalid_limits_raise_value_error(self, overrides: dict[str, float]) -> None:
        with pytest.raises(ValueError):
            IngestionLimits(**overrides)  # type: ignore[arg-type]

    @pytest.mark.parametrize("field", FLOAT_LIMIT_FIELDS)
    @pytest.mark.parametrize("bad", NON_FINITE_FLOATS, ids=NON_FINITE_FLOAT_IDS)
    def test_rejects_non_finite_float_limits(self, field: str, bad: float) -> None:
        """NaN, +inf and -inf are rejected for every float-typed limit."""
        with pytest.raises(ValueError, match="must be finite"):
            IngestionLimits(**{field: bad})  # type: ignore[arg-type]

    def test_limits_accept_overrides(self) -> None:
        limits = IngestionLimits(max_pdf_size_bytes=1024, scanned_page_ratio=0.5)

        assert limits.max_pdf_size_bytes == 1024
        assert limits.scanned_page_ratio == 0.5


class TestSettingsWiring:
    """``app.config.Settings`` adapts environment values into ``IngestionLimits``."""

    def test_defaults_map_to_documented_limits(self) -> None:
        assert load_settings().ingestion_limits == DEFAULT_INGESTION_LIMITS

    def test_environment_overrides_are_honoured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MAX_PDF_SIZE_MB", "7")
        monkeypatch.setenv("SCANNED_PAGE_CHAR_THRESHOLD", "9")
        monkeypatch.setenv("SCANNED_PAGE_RATIO", "0.25")
        monkeypatch.setenv("SCANNED_DENSITY_THRESHOLD", "12.5")
        monkeypatch.setenv("MIN_PDF_PAGE_COUNT", "2")

        limits = load_settings().ingestion_limits

        assert limits.max_pdf_size_bytes == 7 * BYTES_PER_MEGABYTE
        assert limits.scanned_page_char_threshold == 9
        assert limits.scanned_page_ratio == 0.25
        assert limits.scanned_density_threshold == 12.5
        assert limits.min_page_count == 2
