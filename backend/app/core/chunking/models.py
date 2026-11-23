"""Immutable chunk contract for the chunking subsystem.

M1.1 fixes the data contract only; no chunking algorithm is implemented here
(that is M1.5, ``app/core/chunking/semantic.py``). The contract mirrors
SYSTEM_ARCHITECTURE.md section 2.2 exactly.

Invariant (decision D6 / OD-1, closed): a chunk belongs to exactly one page, so it
stores exactly one ``page_number`` and one normalized ``bbox`` covering that page.
A chunk never spans a page boundary, which keeps citation provenance unambiguous.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Chunk:
    """A retrievable, provenance-carrying unit of text.

    ``bbox`` is a normalized ``(x0, y0, x1, y1)`` rectangle in ``[0, 1]`` that
    locates the chunk on ``page_number``.

    ``char_start`` and ``char_end`` are half-open offsets into the parent
    section's text: they delimit a contiguous slice, ``parent_text[char_start:char_end]``,
    whose content is exactly ``text``. For an unmodified slice this means the
    invariant ``char_end - char_start == len(text)`` always holds and is enforced
    here. (A producer that trims or normalizes the shipped ``text`` must therefore
    keep the reported offsets consistent with it rather than with the raw parent
    string.)
    """

    chunk_id: str
    paper_id: str
    section_title: str
    page_number: int
    bbox: tuple[float, float, float, float]
    char_start: int
    char_end: int
    text: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "bbox", tuple(self.bbox))
        if self.page_number < 1:
            raise ValueError(f"Page numbers are 1-based: {self.page_number}.")
        if self.char_start < 0:
            raise ValueError(f"char_start must not be negative: {self.char_start}.")
        if self.char_end < self.char_start:
            raise ValueError(f"char_end={self.char_end} precedes char_start={self.char_start}.")
        if self.char_end - self.char_start != len(self.text):
            raise ValueError(
                f"char_end - char_start ({self.char_end - self.char_start}) must equal "
                f"len(text) ({len(self.text)}): the offsets must index a contiguous slice of "
                "the parent section text whose content is exactly this chunk's text."
            )
        x0, y0, x1, y1 = self.bbox
        for name, value in (("x0", x0), ("y0", y0), ("x1", x1), ("y1", y1)):
            if not math.isfinite(value):
                raise ValueError(f"bbox coordinate {name}={value} must be finite.")
        if not (0.0 <= x0 <= x1 <= 1.0 and 0.0 <= y0 <= y1 <= 1.0):
            raise ValueError(f"bbox must be a normalized ordered rectangle in [0, 1]: {self.bbox}.")
