"""Programmatic, deterministic PDF fixtures for the ingestion test suite.

Fixtures are generated at test time with PyMuPDF instead of being committed as
binary blobs (decision D9): they are diff-reviewable, deterministic, and need no
network access. Each builder returns raw PDF bytes ready to hand to the validator.

The text-bearing fixtures deliberately separate the two signals the validator
cares about - per-page character counts and overall density - so the
document-level scanned detection (decision D5) can be exercised from both sides.
"""

from __future__ import annotations

import pymupdf

PAGE_WIDTH: float = 612.0
PAGE_HEIGHT: float = 792.0

DENSE_REPETITIONS: int = 10
"""Repetitions of the filler sentence used for a "dense" page (~1.5k characters)."""

SPARSE_PAGE_TEXT: str = "Cover"
"""A short caption: fewer than the 50-character sparse threshold."""

_FILLER_SENTENCE: str = (
    "Structure-aware ingestion must preserve the reading order of scientific prose "
    "and retain page-level provenance for every extracted span of text. "
)

_EMPTY_PDF: bytes = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [ ] /Count 0 >>\nendobj\n"
    b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"
)
"""A structurally valid PDF whose page tree is empty (zero pages)."""


def dense_text(repetitions: int = DENSE_REPETITIONS) -> str:
    """Return deterministic prose long enough to count as a non-sparse page."""
    return _FILLER_SENTENCE * repetitions


def build_pdf_bytes(pages: list[str]) -> bytes:
    """Build a PDF with one text page per entry; empty strings yield blank pages."""
    document = pymupdf.open()
    try:
        for text in pages:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            if text:
                page.insert_textbox(pymupdf.Rect(50, 50, PAGE_WIDTH - 50, PAGE_HEIGHT - 50), text)
        return bytes(document.tobytes())
    finally:
        document.close()


def _image_only_pdf_bytes(page_count: int) -> bytes:
    """Build a PDF whose pages carry a raster image and no extractable text."""
    document = pymupdf.open()
    try:
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 64, 64), 0)
        pixmap.clear_with(230)
        for _ in range(page_count):
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            page.insert_image(pymupdf.Rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT), pixmap=pixmap)
        return bytes(document.tobytes())
    finally:
        document.close()


def normal_pdf_bytes() -> bytes:
    """A single dense page: a valid, non-scanned document."""
    return build_pdf_bytes([dense_text()])


def two_page_pdf_bytes() -> bytes:
    """Two dense pages, for page-count and per-page character-count assertions."""
    return build_pdf_bytes([dense_text(), dense_text()])


def sparse_page_pdf_bytes() -> bytes:
    """Two dense pages surrounding one sparse page (a cover page).

    Sparse ratio is 1/3 and density is ~1,000 characters per page, so a correct
    document-level detector must accept this document (decision D5).
    """
    return build_pdf_bytes([dense_text(), SPARSE_PAGE_TEXT, dense_text()])


def scanned_pdf_bytes(page_count: int = 3) -> bytes:
    """An image-only document: every page yields zero extractable characters."""
    return _image_only_pdf_bytes(page_count)


def empty_pdf_bytes() -> bytes:
    """A structurally valid PDF that contains zero pages."""
    return _EMPTY_PDF


def corrupt_pdf_bytes() -> bytes:
    """Valid magic bytes followed by garbage: the PDF cannot be parsed."""
    return b"%PDF-1.4\nthis is not a real pdf body\n%%EOF\n"


def invalid_magic_bytes() -> bytes:
    """A payload that is not a PDF at all (no PDF file signature)."""
    return b"NOT-A-PDF\nplain text pretending to be a document\n"


def encrypted_pdf_bytes(user_password: str = "user", owner_password: str = "owner") -> bytes:
    """A password-protected PDF (AES-256), unreadable without credentials."""
    document = pymupdf.open()
    try:
        page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        page.insert_textbox(pymupdf.Rect(50, 50, PAGE_WIDTH - 50, PAGE_HEIGHT - 50), dense_text())
        return bytes(
            document.tobytes(
                encryption=pymupdf.PDF_ENCRYPT_AES_256,
                owner_pw=owner_password,
                user_pw=user_password,
            )
        )
    finally:
        document.close()


def oversized_pdf_bytes(limit_bytes: int) -> bytes:
    """Bytes that keep the PDF signature but exceed ``limit_bytes``.

    The size ceiling is enforced before the document is opened, so the payload only
    needs a valid signature and a length above the limit.
    """
    header = b"%PDF-1.4\n"
    return header + b"A" * max(0, limit_bytes + 1 - len(header))
