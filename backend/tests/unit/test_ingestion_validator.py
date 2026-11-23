"""Tests for PDF validation: failure paths, statistics and scanned detection."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.core.ingestion.config import IngestionLimits
from app.core.ingestion.exceptions import (
    CorruptPDFException,
    EmptyDocumentException,
    EncryptedPDFException,
    FileTooLargeException,
    ScannedPDFException,
)
from app.core.ingestion.validator import (
    ValidationReport,
    build_validation_report,
    validate_pdf_bytes,
    validate_pdf_path,
)
from tests.fixtures import pdf_factory

SMALL_LIMITS = IngestionLimits(max_pdf_size_bytes=1024)


class TestSuccessfulValidation:
    """A valid scientific PDF passes and yields deterministic statistics."""

    def test_valid_pdf_returns_a_report(self) -> None:
        report = validate_pdf_bytes(pdf_factory.normal_pdf_bytes(), source_name="paper.pdf")

        assert isinstance(report, ValidationReport)
        assert report.source_name == "paper.pdf"
        assert report.is_scanned is False

    def test_page_count_is_correct(self) -> None:
        single = validate_pdf_bytes(pdf_factory.normal_pdf_bytes(), source_name="one.pdf")
        double = validate_pdf_bytes(pdf_factory.two_page_pdf_bytes(), source_name="two.pdf")

        assert single.page_count == 1
        assert double.page_count == 2

    def test_per_page_character_counts_are_reported(self) -> None:
        report = validate_pdf_bytes(pdf_factory.two_page_pdf_bytes(), source_name="two.pdf")

        assert len(report.page_char_counts) == report.page_count
        assert all(count > 50 for count in report.page_char_counts)

    def test_overall_character_density_matches_the_counts(self) -> None:
        report = validate_pdf_bytes(pdf_factory.two_page_pdf_bytes(), source_name="two.pdf")

        expected = report.total_char_count / report.page_count
        assert report.total_char_count == sum(report.page_char_counts)
        assert report.char_density == pytest.approx(expected)
        assert report.char_density > 100.0

    def test_no_sparse_pages_are_reported_for_a_dense_document(self) -> None:
        report = validate_pdf_bytes(pdf_factory.normal_pdf_bytes(), source_name="paper.pdf")

        assert report.sparse_page_count == 0
        assert report.sparse_page_ratio == 0.0

    def test_validation_is_deterministic(self) -> None:
        data = pdf_factory.two_page_pdf_bytes()

        first = validate_pdf_bytes(data, source_name="paper.pdf")
        second = validate_pdf_bytes(data, source_name="paper.pdf")

        assert first == second

    def test_report_is_immutable(self) -> None:
        report = validate_pdf_bytes(pdf_factory.normal_pdf_bytes(), source_name="paper.pdf")

        with pytest.raises(FrozenInstanceError):
            report.page_count = 99  # type: ignore[misc]


class TestDocumentLevelScannedDetection:
    """D5: detection happens at document level, never per page."""

    def test_scanned_document_is_rejected(self) -> None:
        with pytest.raises(ScannedPDFException) as exc_info:
            validate_pdf_bytes(pdf_factory.scanned_pdf_bytes(), source_name="scan.pdf")

        assert exc_info.value.http_status == 422
        assert "scan.pdf" in exc_info.value.message

    def test_single_sparse_page_is_tolerated(self) -> None:
        """A cover page must not reject an otherwise valid paper."""
        report = validate_pdf_bytes(pdf_factory.sparse_page_pdf_bytes(), source_name="paper.pdf")

        assert report.page_count == 3
        assert report.sparse_page_count == 1
        assert report.sparse_page_ratio == pytest.approx(1 / 3)
        assert report.char_density > 100.0
        assert report.is_scanned is False

    def test_build_report_classifies_fully_sparse_document(self) -> None:
        report = build_validation_report("scan.pdf", [0, 0, 0])

        assert report.is_scanned is True
        assert report.sparse_page_ratio == 1.0
        assert report.char_density == 0.0

    def test_document_with_no_pages_is_not_classified_as_scanned(self) -> None:
        report = build_validation_report("empty.pdf", [])

        assert report.page_count == 0
        assert report.is_scanned is False

    def test_sparse_ratio_boundary_is_strict(self) -> None:
        """Exactly 80% sparse is tolerated; above 80% is rejected."""
        tolerated = build_validation_report("paper.pdf", [49, 49, 49, 49, 1000])
        rejected = build_validation_report("scan.pdf", [49, 49, 49, 49, 49, 1000])

        assert tolerated.sparse_page_ratio == pytest.approx(0.8)
        assert tolerated.is_scanned is False
        assert rejected.sparse_page_ratio > 0.80
        assert rejected.is_scanned is True

    def test_density_boundary_is_strict(self) -> None:
        """Exactly 100 characters per page is tolerated; below is rejected."""
        tolerated = build_validation_report("paper.pdf", [100])
        rejected = build_validation_report("scan.pdf", [99])

        assert tolerated.char_density == pytest.approx(100.0)
        assert tolerated.is_scanned is False
        assert rejected.is_scanned is True

    def test_sparse_page_threshold_is_strict(self) -> None:
        """A page with exactly 50 characters is not sparse."""
        exactly_at_threshold = build_validation_report("paper.pdf", [50, 1000])
        just_below = build_validation_report("paper.pdf", [49, 1000])

        assert exactly_at_threshold.sparse_page_count == 0
        assert just_below.sparse_page_count == 1


class TestValidationFailurePaths:
    """Every failure path raises its specific typed exception."""

    def test_corrupt_pdf_raises_corrupt_exception(self) -> None:
        with pytest.raises(CorruptPDFException) as exc_info:
            validate_pdf_bytes(pdf_factory.corrupt_pdf_bytes(), source_name="broken.pdf")

        assert exc_info.value.http_status == 400

    def test_invalid_magic_bytes_raise_corrupt_exception(self) -> None:
        with pytest.raises(CorruptPDFException, match="missing the '%PDF-' signature"):
            validate_pdf_bytes(pdf_factory.invalid_magic_bytes(), source_name="note.txt")

    def test_empty_payload_raises_corrupt_exception(self) -> None:
        with pytest.raises(CorruptPDFException):
            validate_pdf_bytes(b"", source_name="empty.bin")

    def test_zero_page_document_raises_empty_document_exception(self) -> None:
        with pytest.raises(EmptyDocumentException) as exc_info:
            validate_pdf_bytes(pdf_factory.empty_pdf_bytes(), source_name="void.pdf")

        assert exc_info.value.http_status == 400
        assert "void.pdf" in exc_info.value.message

    def test_encrypted_pdf_raises_encrypted_exception(self) -> None:
        with pytest.raises(EncryptedPDFException) as exc_info:
            validate_pdf_bytes(pdf_factory.encrypted_pdf_bytes(), source_name="secret.pdf")

        assert exc_info.value.http_status == 422

    def test_oversized_payload_raises_file_too_large_exception(self) -> None:
        payload = pdf_factory.oversized_pdf_bytes(SMALL_LIMITS.max_pdf_size_bytes)

        with pytest.raises(FileTooLargeException) as exc_info:
            validate_pdf_bytes(payload, source_name="huge.pdf", limits=SMALL_LIMITS)

        assert type(exc_info.value) is FileTooLargeException
        assert exc_info.value.http_status == 413
        assert "huge.pdf" in exc_info.value.message
        assert "ingestion limit" in exc_info.value.message

    def test_size_ceiling_is_inclusive(self) -> None:
        """A payload exactly at the ceiling is accepted."""
        limits = IngestionLimits(max_pdf_size_bytes=len(pdf_factory.normal_pdf_bytes()))
        report = validate_pdf_bytes(
            pdf_factory.normal_pdf_bytes(), source_name="paper.pdf", limits=limits
        )

        assert report.page_count == 1

    def test_magic_bytes_are_checked_before_size(self) -> None:
        """A non-PDF that is also oversized is reported as corrupt, not oversized."""
        payload = b"NOTPDF" + b"A" * (SMALL_LIMITS.max_pdf_size_bytes * 2)

        with pytest.raises(CorruptPDFException):
            validate_pdf_bytes(payload, source_name="note.txt", limits=SMALL_LIMITS)

    def test_oversized_non_pdf_payload_is_reported_as_corrupt(self) -> None:
        """Bytes entry point: signature wins over size."""
        payload = b"NOTPDF" + b"A" * (SMALL_LIMITS.max_pdf_size_bytes * 2)

        with pytest.raises(CorruptPDFException) as exc_info:
            validate_pdf_bytes(payload, source_name="note.txt", limits=SMALL_LIMITS)

        assert type(exc_info.value) is CorruptPDFException


class TestPathValidation:
    """Filesystem-path entrypoint mirrors byte validation."""

    def test_valid_file_is_accepted_and_named_after_the_path(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "attention.pdf"
        pdf_path.write_bytes(pdf_factory.normal_pdf_bytes())

        report = validate_pdf_path(pdf_path)

        assert report.source_name == "attention.pdf"
        assert report.page_count == 1
        assert report.is_scanned is False

    def test_file_larger_than_the_ceiling_raises_file_too_large_exception(
        self, tmp_path: Path
    ) -> None:
        pdf_path = tmp_path / "huge.pdf"
        pdf_path.write_bytes(pdf_factory.oversized_pdf_bytes(SMALL_LIMITS.max_pdf_size_bytes))

        with pytest.raises(FileTooLargeException) as exc_info:
            validate_pdf_path(pdf_path, limits=SMALL_LIMITS)

        assert type(exc_info.value) is FileTooLargeException
        assert exc_info.value.http_status == 413
        assert "huge.pdf" in exc_info.value.message
        assert "ingestion limit" in exc_info.value.message

    def test_scanned_file_is_rejected(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "scan.pdf"
        pdf_path.write_bytes(pdf_factory.scanned_pdf_bytes())

        with pytest.raises(ScannedPDFException):
            validate_pdf_path(pdf_path)

    def test_path_and_bytes_entrypoints_agree(self, tmp_path: Path) -> None:
        data = pdf_factory.two_page_pdf_bytes()
        pdf_path = tmp_path / "paper.pdf"
        pdf_path.write_bytes(data)

        assert validate_pdf_path(pdf_path) == validate_pdf_bytes(data, source_name="paper.pdf")

    def test_oversized_non_pdf_file_is_reported_as_corrupt(self, tmp_path: Path) -> None:
        """Path entry point: signature wins over size, matching the bytes entry point."""
        txt_path = tmp_path / "notes.txt"
        txt_path.write_bytes(b"NOTPDF" + b"A" * (SMALL_LIMITS.max_pdf_size_bytes * 2))

        with pytest.raises(CorruptPDFException) as exc_info:
            validate_pdf_path(txt_path, limits=SMALL_LIMITS)

        assert type(exc_info.value) is CorruptPDFException

    def test_entrypoints_agree_on_an_oversized_non_pdf(self, tmp_path: Path) -> None:
        payload = b"NOTPDF" + b"A" * (SMALL_LIMITS.max_pdf_size_bytes * 2)
        txt_path = tmp_path / "notes.txt"
        txt_path.write_bytes(payload)

        with pytest.raises(CorruptPDFException):
            validate_pdf_bytes(payload, source_name="notes.txt", limits=SMALL_LIMITS)
        with pytest.raises(CorruptPDFException):
            validate_pdf_path(txt_path, limits=SMALL_LIMITS)


class TestValidationReportInvariants:
    """A report can never claim statistics that disagree with its per-page counts."""

    def test_rejects_negative_per_page_counts(self) -> None:
        with pytest.raises(ValueError, match="must not be negative"):
            build_validation_report("paper.pdf", [3, -1, 4])

    def test_rejects_page_count_mismatch(self) -> None:
        with pytest.raises(ValueError, match="page_count=2"):
            ValidationReport(
                source_name="paper.pdf",
                page_count=2,
                page_char_counts=(1, 2, 3),
                total_char_count=6,
                char_density=2.0,
                sparse_page_count=0,
                sparse_page_ratio=0.0,
                is_scanned=False,
            )

    def test_rejects_total_char_count_mismatch(self) -> None:
        with pytest.raises(ValueError, match="total_char_count="):
            ValidationReport(
                source_name="paper.pdf",
                page_count=2,
                page_char_counts=(1, 2),
                total_char_count=99,
                char_density=1.5,
                sparse_page_count=0,
                sparse_page_ratio=0.0,
                is_scanned=False,
            )

    def test_rejects_char_density_mismatch(self) -> None:
        with pytest.raises(ValueError, match="char_density="):
            ValidationReport(
                source_name="paper.pdf",
                page_count=2,
                page_char_counts=(1, 2),
                total_char_count=3,
                char_density=9.0,
                sparse_page_count=0,
                sparse_page_ratio=0.0,
                is_scanned=False,
            )

    def test_rejects_sparse_page_count_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="sparse_page_count=3"):
            ValidationReport(
                source_name="paper.pdf",
                page_count=2,
                page_char_counts=(1, 2),
                total_char_count=3,
                char_density=1.5,
                sparse_page_count=3,
                sparse_page_ratio=1.5,
                is_scanned=True,
            )

    def test_canonicalizes_page_char_counts_from_a_list(self) -> None:
        counts = [1, 2]
        report = ValidationReport(
            source_name="paper.pdf",
            page_count=2,
            page_char_counts=counts,  # type: ignore[arg-type]
            total_char_count=3,
            char_density=1.5,
            sparse_page_count=0,
            sparse_page_ratio=0.0,
            is_scanned=False,
        )

        assert isinstance(report.page_char_counts, tuple)
        counts.append(3)
        assert report.page_char_counts == (1, 2)

    def test_zero_page_report_stays_consistent(self) -> None:
        report = build_validation_report("empty.pdf", [])

        assert report.page_count == 0
        assert report.page_char_counts == ()
        assert report.total_char_count == 0
        assert report.char_density == 0.0
        assert report.sparse_page_count == 0
        assert report.sparse_page_ratio == 0.0
        assert report.is_scanned is False
