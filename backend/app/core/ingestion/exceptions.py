"""Typed, framework-free domain exceptions for the ingestion pipeline.

The ingestion layer must never import FastAPI, Starlette or SQLAlchemy. Domain
failures are therefore modelled as plain Python exceptions, and each exception
exposes an ``http_status`` attribute so the future API layer can translate a
domain failure into an HTTP response without ``app/core`` depending on a web
framework.

Status mappings (M1_ARCHITECTURE.md, decision D10):

- :class:`CorruptPDFException`    -> 400
- :class:`EmptyDocumentException` -> 400
- :class:`FileTooLargeException`  -> 413
- :class:`EncryptedPDFException`  -> 422
- :class:`ScannedPDFException`    -> 422
"""

from __future__ import annotations


class IngestionError(Exception):
    """Base class for every ingestion domain failure.

    ``http_status`` defaults to a generic 400 client-error mapping. Concrete
    subclasses override it with the status code prescribed by the design, and may
    override ``default_message`` to provide an actionable fallback.
    """

    http_status: int = 400
    default_message: str = "PDF ingestion failed."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class CorruptPDFException(IngestionError):
    """The payload is not a PDF, or the PDF structure cannot be parsed."""

    http_status = 400
    default_message = "The file is not a valid or readable PDF."


class EmptyDocumentException(IngestionError):
    """The payload opened successfully but contains no pages."""

    http_status = 400
    default_message = "The PDF contains no pages."


class EncryptedPDFException(IngestionError):
    """The PDF is password-protected and cannot be read without credentials."""

    http_status = 422
    default_message = "The PDF is encrypted and requires a password to be read."


class FileTooLargeException(IngestionError):
    """The payload exceeds the configured maximum ingestion size."""

    http_status = 413
    default_message = "The PDF exceeds the maximum permitted size."


class ScannedPDFException(IngestionError):
    """The document carries no meaningful extractable text (image-only PDF)."""

    http_status = 422
    default_message = (
        "The PDF appears to be a scanned or image-only document with no extractable text."
    )
