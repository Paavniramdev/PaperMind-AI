"""Tests for the typed ingestion exception hierarchy (decision D10)."""

from __future__ import annotations

import pytest

from app.core.ingestion.exceptions import (
    CorruptPDFException,
    EmptyDocumentException,
    EncryptedPDFException,
    FileTooLargeException,
    IngestionError,
    ScannedPDFException,
)

STATUS_MAPPINGS: tuple[tuple[type[IngestionError], int], ...] = (
    (CorruptPDFException, 400),
    (EmptyDocumentException, 400),
    (FileTooLargeException, 413),
    (EncryptedPDFException, 422),
    (ScannedPDFException, 422),
)
EXCEPTION_TYPES = tuple(exception_type for exception_type, _ in STATUS_MAPPINGS)


@pytest.mark.parametrize("exception_type", EXCEPTION_TYPES)
def test_every_exception_inherits_from_ingestion_error(
    exception_type: type[IngestionError],
) -> None:
    """Every domain failure is catchable through the common base class."""
    assert issubclass(exception_type, IngestionError)


@pytest.mark.parametrize(("exception_type", "expected_status"), STATUS_MAPPINGS)
def test_exception_exposes_prescribed_http_status(
    exception_type: type[IngestionError], expected_status: int
) -> None:
    """Each exception carries the HTTP status prescribed by the design."""
    assert exception_type.http_status == expected_status


@pytest.mark.parametrize("exception_type", EXCEPTION_TYPES)
def test_exception_instances_expose_http_status(exception_type: type[IngestionError]) -> None:
    """The status is reachable from an instance, not only from the class."""
    assert exception_type().http_status == exception_type.http_status


def test_base_error_defaults_to_client_error_status() -> None:
    """The base failure mapping is a client error (400)."""
    assert IngestionError.http_status == 400
    assert IngestionError("boom").http_status == 400


@pytest.mark.parametrize("exception_type", EXCEPTION_TYPES)
def test_default_message_is_actionable(exception_type: type[IngestionError]) -> None:
    """A message-less failure still reports a specific, non-empty reason."""
    error = exception_type()

    assert error.message == exception_type.default_message
    assert str(error) == exception_type.default_message
    assert str(error).strip()


@pytest.mark.parametrize("exception_type", EXCEPTION_TYPES)
def test_custom_message_overrides_default(exception_type: type[IngestionError]) -> None:
    """A supplied message is preserved verbatim."""
    error = exception_type("specific failure reason")

    assert error.message == "specific failure reason"
    assert str(error) == "specific failure reason"


def test_exceptions_are_individually_catchable() -> None:
    """A specific failure can be caught without catching unrelated ones."""
    with pytest.raises(EncryptedPDFException):
        raise EncryptedPDFException()

    with pytest.raises(IngestionError):
        raise ScannedPDFException()


def test_exception_types_are_distinct() -> None:
    """No two concrete exceptions collapse into the same class."""
    assert len(set(EXCEPTION_TYPES)) == len(STATUS_MAPPINGS)
