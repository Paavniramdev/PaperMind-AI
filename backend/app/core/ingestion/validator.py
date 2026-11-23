"""Deterministic PDF validation for the ingestion pipeline.

Validation is fail-fast and always follows the same order
(M1_ARCHITECTURE.md, section 2):

1. PDF magic-byte validation.
2. Configurable maximum file-size validation.
3. PDF opening and corruption detection.
4. Encryption detection.
5. Page-count validation.
6. Document-level scanned-document detection (decision D5).

Both entry points (:func:`validate_pdf_bytes` and :func:`validate_pdf_path`)
enforce this order, so they raise the same exception for the same defective
input regardless of how the bytes are supplied.

The module produces an immutable :class:`ValidationReport` and never generates
identifiers, so identical input always yields identical output. The PyMuPDF
document handle never escapes: it is closed before the report is returned, and no
PyMuPDF type appears in any public signature.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from app.core.ingestion.config import (
    BYTES_PER_MEGABYTE,
    DEFAULT_INGESTION_LIMITS,
    IngestionLimits,
)
from app.core.ingestion.exceptions import (
    CorruptPDFException,
    EmptyDocumentException,
    EncryptedPDFException,
    FileTooLargeException,
    ScannedPDFException,
)

PDF_MAGIC_BYTES: bytes = b"%PDF-"
"""File signature carried by every PDF (ISO 32000-1, 7.5.2)."""

_OPEN_ERRORS: tuple[type[Exception], ...] = (RuntimeError, ValueError)
"""Exceptions PyMuPDF raises when a stream cannot be parsed as a PDF.

``pymupdf.FileDataError`` and ``pymupdf.EmptyFileError`` both derive from
``RuntimeError`` and are re-raised as :class:`CorruptPDFException`.
"""


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Immutable, deterministic statistics from a successful validation.

    Construction enforces internal consistency, so a report can never claim a
    page count, total or density that disagrees with its per-page counts.
    ``page_char_counts`` is canonicalized to a tuple.
    """

    source_name: str
    page_count: int
    page_char_counts: tuple[int, ...]
    total_char_count: int
    char_density: float
    sparse_page_count: int
    sparse_page_ratio: float
    is_scanned: bool

    def __post_init__(self) -> None:
        counts = tuple(self.page_char_counts)
        object.__setattr__(self, "page_char_counts", counts)
        if any(count < 0 for count in counts):
            raise ValueError(f"Per-page character counts must not be negative: {counts}.")
        if self.page_count != len(counts):
            raise ValueError(
                f"page_count={self.page_count} must equal the number of per-page "
                f"character counts ({len(counts)})."
            )
        expected_total = sum(counts)
        if self.total_char_count != expected_total:
            raise ValueError(
                f"total_char_count={self.total_char_count} must equal the sum of the "
                f"per-page character counts ({expected_total})."
            )
        if not 0 <= self.sparse_page_count <= self.page_count:
            raise ValueError(
                f"sparse_page_count={self.sparse_page_count} must be within "
                f"[0, page_count={self.page_count}]."
            )
        expected_density = expected_total / self.page_count if self.page_count else 0.0
        if self.char_density != expected_density:
            raise ValueError(
                f"char_density={self.char_density} must equal total_char_count / page_count "
                f"({expected_density})."
            )
        expected_ratio = self.sparse_page_count / self.page_count if self.page_count else 0.0
        if self.sparse_page_ratio != expected_ratio:
            raise ValueError(
                f"sparse_page_ratio={self.sparse_page_ratio} must equal sparse_page_count / "
                f"page_count ({expected_ratio})."
            )


def build_validation_report(
    source_name: str,
    page_char_counts: Sequence[int],
    limits: IngestionLimits = DEFAULT_INGESTION_LIMITS,
) -> ValidationReport:
    """Classify a document from its per-page character counts (pure, no I/O).

    Implements D5 at document level: a document is scanned when more than
    ``scanned_page_ratio`` of its pages are sparse (fewer than
    ``scanned_page_char_threshold`` characters), or when its overall text density
    is below ``scanned_density_threshold`` characters per page. A single sparse
    page therefore never rejects an otherwise valid document.
    """
    counts = tuple(page_char_counts)
    if any(count < 0 for count in counts):
        raise ValueError(f"Per-page character counts must not be negative: {counts}.")
    page_count = len(counts)
    total_char_count = sum(counts)
    char_density = total_char_count / page_count if page_count else 0.0
    sparse_page_count = sum(1 for count in counts if count < limits.scanned_page_char_threshold)
    sparse_page_ratio = sparse_page_count / page_count if page_count else 0.0
    is_scanned = page_count > 0 and (
        sparse_page_ratio > limits.scanned_page_ratio
        or char_density < limits.scanned_density_threshold
    )
    return ValidationReport(
        source_name=source_name,
        page_count=page_count,
        page_char_counts=counts,
        total_char_count=total_char_count,
        char_density=char_density,
        sparse_page_count=sparse_page_count,
        sparse_page_ratio=sparse_page_ratio,
        is_scanned=is_scanned,
    )


def _size_exceeded_message(source_name: str, size: int, max_size: int) -> str:
    megabytes = BYTES_PER_MEGABYTE
    return (
        f"{source_name!r} is {size / megabytes:.1f} MiB which exceeds the "
        f"{max_size / megabytes:.1f} MiB ingestion limit."
    )


def _require_pdf_signature(prefix: bytes, source_name: str) -> None:
    """Reject anything that does not begin with the PDF file signature.

    Only ``len(PDF_MAGIC_BYTES)`` bytes are needed, so the caller can supply a
    short header read instead of the whole file.
    """
    if not prefix.startswith(PDF_MAGIC_BYTES):
        raise CorruptPDFException(
            f"{source_name!r} is not a PDF: missing the {PDF_MAGIC_BYTES.decode()!r} signature."
        )


def _open_document(data: bytes, source_name: str) -> pymupdf.Document:
    try:
        return pymupdf.open(stream=data, filetype="pdf")
    except _OPEN_ERRORS as exc:
        raise CorruptPDFException(f"{source_name!r} could not be parsed as a PDF: {exc}") from exc


def validate_pdf_bytes(
    data: bytes,
    *,
    source_name: str,
    limits: IngestionLimits = DEFAULT_INGESTION_LIMITS,
) -> ValidationReport:
    """Validate an in-memory PDF and return its :class:`ValidationReport`.

    Raises one of :class:`CorruptPDFException`, :class:`FileTooLargeException` (size
    ceiling), :class:`EncryptedPDFException`, :class:`EmptyDocumentException` or
    :class:`ScannedPDFException` when the corresponding check fails.
    """
    _require_pdf_signature(data, source_name)
    if len(data) > limits.max_pdf_size_bytes:
        raise FileTooLargeException(
            _size_exceeded_message(source_name, len(data), limits.max_pdf_size_bytes)
        )

    document = _open_document(data, source_name)
    try:
        if document.needs_pass:
            raise EncryptedPDFException(f"{source_name!r} is password-protected.")
        page_count = document.page_count
        if page_count < limits.min_page_count:
            raise EmptyDocumentException(f"{source_name!r} contains no pages.")
        page_char_counts = tuple(
            len(document.load_page(index).get_text()) for index in range(page_count)
        )
    finally:
        document.close()

    report = build_validation_report(source_name, page_char_counts, limits)
    if report.is_scanned:
        raise ScannedPDFException(
            f"{source_name!r} appears to be scanned: {report.sparse_page_count}/"
            f"{report.page_count} sparse pages, density {report.char_density:.1f} characters/page."
        )
    return report


def validate_pdf_path(
    path: str | Path,
    *,
    limits: IngestionLimits = DEFAULT_INGESTION_LIMITS,
) -> ValidationReport:
    """Validate a PDF on disk, using the file name as ``source_name``.

    Externally observable error precedence is identical to
    :func:`validate_pdf_bytes`: signature first, then size, then the remaining
    checks. The trade-off that keeps this cheap is that only the five signature
    bytes are read before the stat-based size check, so an oversized file is
    never loaded into memory and a non-PDF file is still reported as corrupt
    rather than oversized. The full contents are read only once the ceiling has
    passed; the subsequent signature and size checks inside
    :func:`validate_pdf_bytes` are therefore redundant but harmless.
    """
    resolved = Path(path)
    source_name = resolved.name
    with resolved.open("rb") as handle:
        signature = handle.read(len(PDF_MAGIC_BYTES))
    _require_pdf_signature(signature, source_name)
    size = resolved.stat().st_size
    if size > limits.max_pdf_size_bytes:
        raise FileTooLargeException(
            _size_exceeded_message(source_name, size, limits.max_pdf_size_bytes)
        )
    return validate_pdf_bytes(resolved.read_bytes(), source_name=source_name, limits=limits)
