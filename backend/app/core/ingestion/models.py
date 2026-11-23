"""Immutable, framework-free domain models for the ingestion stage.

Every model is a frozen dataclass holding only plain Python data. That guarantees
the properties the design requires (M1_ARCHITECTURE.md, section 1.4):

1. PyMuPDF types never leak out of the parser into the public domain API.
2. Instances are immutable, so downstream stages cannot mutate parse results.
3. Construction validates invariants eagerly and deterministically.
4. Tuple-typed collections are canonicalized in ``__post_init__``, so a mutable
   list handed to a constructor cannot later be mutated through the model, and
   every numeric geometry/dimension is required to be finite.

Invariant violations raise :class:`ValueError`: they indicate a programming error
in a producer stage, not a user-facing ingestion failure (which would be one of
the typed exceptions in :mod:`app.core.ingestion.exceptions`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

Column = Literal["left", "right", "spanning", "single"]
"""Reading-order column label for a layout block.

- ``single``   - page has no column structure.
- ``left``     - left column of a two-column region.
- ``right``    - right column of a two-column region.
- ``spanning`` - full-width block (title, abstract, wide table) crossing columns.
"""

COLUMN_VALUES: tuple[Column, ...] = ("left", "right", "spanning", "single")


@dataclass(frozen=True, slots=True)
class BlockGeometry:
    """Geometry of one layout block, in raw points and normalized coordinates.

    Raw PDF points (``x0, y0, x1, y1``) drive tests and debugging. Normalized
    coordinates (``nx0, ny0, nx1, ny1``) are page-relative values in ``[0, 1]``
    that survive rendering at any zoom level and are what the persistence layer
    and the frontend highlight overlay consume (decision D4).
    """

    x0: float
    y0: float
    x1: float
    y1: float
    nx0: float
    ny0: float
    nx1: float
    ny1: float

    def __post_init__(self) -> None:
        for name, value in (
            ("x0", self.x0),
            ("y0", self.y0),
            ("x1", self.x1),
            ("y1", self.y1),
        ):
            if not math.isfinite(value):
                raise ValueError(f"Raw coordinate {name}={value} must be finite.")
        if self.x0 > self.x1 or self.y0 > self.y1:
            raise ValueError(
                f"Raw coordinates must be ordered: x0={self.x0} <= x1={self.x1}, "
                f"y0={self.y0} <= y1={self.y1}."
            )
        for name, value in (
            ("nx0", self.nx0),
            ("ny0", self.ny0),
            ("nx1", self.nx1),
            ("ny1", self.ny1),
        ):
            if not math.isfinite(value):
                raise ValueError(f"Normalized coordinate {name}={value} must be finite.")
        if self.nx0 > self.nx1 or self.ny0 > self.ny1:
            raise ValueError(
                f"Normalized coordinates must be ordered: nx0={self.nx0} <= nx1={self.nx1}, "
                f"ny0={self.ny0} <= ny1={self.ny1}."
            )
        for name, value in (
            ("nx0", self.nx0),
            ("ny0", self.ny0),
            ("nx1", self.nx1),
            ("ny1", self.ny1),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"Normalized coordinate {name}={value} must be within [0, 1].")


@dataclass(frozen=True, slots=True)
class LayoutBlock:
    """A paragraph-like text unit in true reading order within its page."""

    order: int
    text: str
    geometry: BlockGeometry
    column: Column
    page_number: int

    def __post_init__(self) -> None:
        if self.order < 0:
            raise ValueError(f"Block order must not be negative: {self.order}.")
        if self.page_number < 1:
            raise ValueError(f"Page numbers are 1-based: {self.page_number}.")
        if self.column not in COLUMN_VALUES:
            raise ValueError(f"Unknown column {self.column!r}; expected one of {COLUMN_VALUES}.")


@dataclass(frozen=True, slots=True)
class PageLayout:
    """The reconstructed layout of a single page."""

    page_number: int
    width: float
    height: float
    blocks: tuple[LayoutBlock, ...]
    char_count: int
    is_sparse: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "blocks", tuple(self.blocks))
        if self.page_number < 1:
            raise ValueError(f"Page numbers are 1-based: {self.page_number}.")
        if not math.isfinite(self.width) or not math.isfinite(self.height):
            raise ValueError(f"Page dimensions must be finite: {self.width} x {self.height}.")
        if self.width <= 0.0 or self.height <= 0.0:
            raise ValueError(f"Page dimensions must be positive: {self.width} x {self.height}.")
        if self.char_count < 0:
            raise ValueError(f"char_count must not be negative: {self.char_count}.")


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    """Document-level metadata for an ingested paper."""

    title: str | None
    authors: tuple[str, ...]
    page_count: int
    source_name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "authors", tuple(self.authors))
        if self.page_count < 1:
            raise ValueError(
                f"A parsed document has at least one page: page_count={self.page_count}."
            )
