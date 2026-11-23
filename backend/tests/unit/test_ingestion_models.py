"""Tests for the immutable ingestion models and the chunk contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.core.chunking.models import Chunk
from app.core.ingestion.models import (
    COLUMN_VALUES,
    BlockGeometry,
    DocumentMetadata,
    LayoutBlock,
    PageLayout,
)


def make_geometry() -> BlockGeometry:
    """A representative, valid geometry."""
    return BlockGeometry(
        x0=10.0,
        y0=20.0,
        x1=110.0,
        y1=220.0,
        nx0=0.05,
        ny0=0.10,
        nx1=0.45,
        ny1=0.80,
    )


def make_block() -> LayoutBlock:
    """A representative, valid layout block."""
    return LayoutBlock(
        order=0,
        text="Introduction",
        geometry=make_geometry(),
        column="single",
        page_number=1,
    )


class TestBlockGeometry:
    """Raw and normalized coordinate validation."""

    def test_accepts_consistent_coordinates(self) -> None:
        geometry = make_geometry()

        assert (geometry.x0, geometry.y0, geometry.x1, geometry.y1) == (10.0, 20.0, 110.0, 220.0)
        assert (geometry.nx0, geometry.ny0, geometry.nx1, geometry.ny1) == (0.05, 0.1, 0.45, 0.8)

    def test_accepts_degenerate_but_ordered_raw_coordinates(self) -> None:
        geometry = BlockGeometry(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        assert geometry.x1 == geometry.x0

    @pytest.mark.parametrize(
        "coordinates",
        [
            (200.0, 20.0, 100.0, 220.0, 0.05, 0.1, 0.45, 0.8),
            (10.0, 300.0, 110.0, 220.0, 0.05, 0.1, 0.45, 0.8),
        ],
    )
    def test_rejects_inverted_raw_coordinates(self, coordinates: tuple[float, ...]) -> None:
        with pytest.raises(ValueError, match="Raw coordinates must be ordered"):
            BlockGeometry(*coordinates)

    def test_rejects_inverted_normalized_coordinates(self) -> None:
        with pytest.raises(ValueError, match="Normalized coordinates must be ordered"):
            BlockGeometry(10.0, 20.0, 110.0, 220.0, 0.6, 0.1, 0.4, 0.8)

    @pytest.mark.parametrize(
        "normalized",
        [
            (-0.01, 0.1, 0.5, 0.8),
            (0.05, 0.1, 1.01, 0.8),
            (0.05, 0.1, 2.0, 0.8),
            (0.05, -0.5, 0.5, 0.8),
            (0.05, 0.1, 0.5, 1.5),
        ],
    )
    def test_rejects_normalized_coordinates_outside_unit_range(
        self, normalized: tuple[float, float, float, float]
    ) -> None:
        nx0, ny0, nx1, ny1 = normalized

        with pytest.raises(ValueError, match="must be within \\[0, 1\\]"):
            BlockGeometry(10.0, 20.0, 110.0, 220.0, nx0, ny0, nx1, ny1)

    def test_rejects_not_a_number(self) -> None:
        with pytest.raises(ValueError, match="must be finite"):
            BlockGeometry(10.0, 20.0, 110.0, 220.0, float("nan"), 0.1, 0.5, 0.8)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_rejects_non_finite_raw_coordinates(self, bad: float) -> None:
        with pytest.raises(ValueError, match="must be finite"):
            BlockGeometry(bad, 20.0, 110.0, 220.0, 0.05, 0.1, 0.45, 0.8)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_rejects_non_finite_normalized_coordinates(self, bad: float) -> None:
        with pytest.raises(ValueError, match="must be finite"):
            BlockGeometry(10.0, 20.0, 110.0, 220.0, 0.05, 0.1, bad, 0.8)

    def test_is_immutable(self) -> None:
        geometry = make_geometry()

        with pytest.raises(FrozenInstanceError):
            geometry.x0 = 0.0  # type: ignore[misc]


class TestLayoutBlock:
    """Reading-order index, column label and page number validation."""

    def test_accepts_every_documented_column(self) -> None:
        for column in COLUMN_VALUES:
            block = LayoutBlock(
                order=1,
                text="Body",
                geometry=make_geometry(),
                column=column,
                page_number=2,
            )
            assert block.column == column

    def test_rejects_unknown_column(self) -> None:
        with pytest.raises(ValueError, match="Unknown column"):
            LayoutBlock(
                order=0,
                text="Body",
                geometry=make_geometry(),
                column="middle",  # type: ignore[arg-type]
                page_number=1,
            )

    def test_rejects_negative_order(self) -> None:
        with pytest.raises(ValueError, match="order must not be negative"):
            LayoutBlock(
                order=-1,
                text="Body",
                geometry=make_geometry(),
                column="single",
                page_number=1,
            )

    def test_rejects_zero_page_number(self) -> None:
        with pytest.raises(ValueError, match="1-based"):
            LayoutBlock(
                order=0,
                text="Body",
                geometry=make_geometry(),
                column="single",
                page_number=0,
            )

    def test_is_immutable(self) -> None:
        block = make_block()

        with pytest.raises(FrozenInstanceError):
            block.text = "changed"  # type: ignore[misc]


class TestPageLayout:
    """Page-level layout validation."""

    def test_accepts_valid_page(self) -> None:
        page = PageLayout(
            page_number=1,
            width=612.0,
            height=792.0,
            blocks=(make_block(),),
            char_count=12,
            is_sparse=False,
        )

        assert page.blocks[0].order == 0
        assert page.width == 612.0

    def test_accepts_page_without_blocks(self) -> None:
        page = PageLayout(
            page_number=3, width=612.0, height=792.0, blocks=(), char_count=0, is_sparse=True
        )

        assert page.blocks == ()
        assert page.is_sparse is True

    @pytest.mark.parametrize(("width", "height"), [(0.0, 792.0), (612.0, 0.0), (-1.0, -1.0)])
    def test_rejects_non_positive_dimensions(self, width: float, height: float) -> None:
        with pytest.raises(ValueError, match="dimensions must be positive"):
            PageLayout(
                page_number=1,
                width=width,
                height=height,
                blocks=(),
                char_count=0,
                is_sparse=False,
            )

    def test_rejects_negative_char_count(self) -> None:
        with pytest.raises(ValueError, match="char_count must not be negative"):
            PageLayout(
                page_number=1,
                width=612.0,
                height=792.0,
                blocks=(),
                char_count=-1,
                is_sparse=False,
            )

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_rejects_non_finite_dimensions(self, bad: float) -> None:
        with pytest.raises(ValueError, match="dimensions must be finite"):
            PageLayout(
                page_number=1,
                width=bad,
                height=792.0,
                blocks=(),
                char_count=0,
                is_sparse=False,
            )

    def test_blocks_are_canonicalized_from_a_list(self) -> None:
        source = [make_block()]
        page = PageLayout(
            page_number=1,
            width=612.0,
            height=792.0,
            blocks=source,  # type: ignore[arg-type]
            char_count=12,
            is_sparse=False,
        )

        assert isinstance(page.blocks, tuple)
        source.append(make_block())
        assert len(page.blocks) == 1

    def test_is_immutable(self) -> None:
        page = PageLayout(
            page_number=1, width=612.0, height=792.0, blocks=(), char_count=0, is_sparse=True
        )

        with pytest.raises(FrozenInstanceError):
            page.page_number = 2  # type: ignore[misc]


class TestDocumentMetadata:
    """Document-level metadata validation."""

    def test_accepts_metadata_with_title_and_authors(self) -> None:
        metadata = DocumentMetadata(
            title="Attention Is All You Need",
            authors=("Vaswani", "Shazeer"),
            page_count=11,
            source_name="attention.pdf",
        )

        assert metadata.authors == ("Vaswani", "Shazeer")
        assert metadata.page_count == 11

    def test_accepts_missing_title(self) -> None:
        metadata = DocumentMetadata(title=None, authors=(), page_count=1, source_name="x.pdf")

        assert metadata.title is None
        assert metadata.authors == ()

    def test_rejects_zero_pages(self) -> None:
        with pytest.raises(ValueError, match="at least one page"):
            DocumentMetadata(title=None, authors=(), page_count=0, source_name="x.pdf")

    def test_authors_are_canonicalized_from_a_list(self) -> None:
        source = ["Vaswani"]
        metadata = DocumentMetadata(
            title=None,
            authors=source,  # type: ignore[arg-type]
            page_count=1,
            source_name="x.pdf",
        )

        assert isinstance(metadata.authors, tuple)
        source.append("Shazeer")
        assert metadata.authors == ("Vaswani",)

    def test_is_immutable(self) -> None:
        metadata = DocumentMetadata(title=None, authors=(), page_count=1, source_name="x.pdf")

        with pytest.raises(FrozenInstanceError):
            metadata.page_count = 5  # type: ignore[misc]


class TestChunk:
    """The OD-1 chunk contract: exactly one page provenance per chunk."""

    def make_chunk(self, **overrides: object) -> Chunk:
        values: dict[str, object] = {
            "chunk_id": "c_0f8fad5b",
            "paper_id": "p_9a4c1e2d",
            "section_title": "3. Methodology",
            "page_number": 4,
            "bbox": (0.12, 0.34, 0.48, 0.65),
            "char_start": 1240,
            "char_end": 1264,
            "text": "structure-aware chunking",
        }
        values.update(overrides)
        return Chunk(**values)  # type: ignore[arg-type]

    def test_accepts_the_documented_contract(self) -> None:
        chunk = self.make_chunk()

        assert chunk.page_number == 4
        assert chunk.bbox == (0.12, 0.34, 0.48, 0.65)
        assert chunk.char_end - chunk.char_start == 24
        assert chunk.char_end - chunk.char_start == len(chunk.text)

    def test_offsets_span_exactly_the_text_length(self) -> None:
        text = "structure-aware chunking"
        chunk = self.make_chunk(char_start=500, char_end=500 + len(text))

        assert chunk.char_end - chunk.char_start == len(chunk.text)

    def test_rejects_offsets_inconsistent_with_text_length(self) -> None:
        with pytest.raises(ValueError, match=r"must equal len\(text\)"):
            self.make_chunk(char_start=0, char_end=25)

    def test_rejects_zero_page_number(self) -> None:
        with pytest.raises(ValueError, match="1-based"):
            self.make_chunk(page_number=0)

    def test_rejects_negative_char_start(self) -> None:
        with pytest.raises(ValueError, match="char_start must not be negative"):
            self.make_chunk(char_start=-1)

    def test_rejects_reversed_char_offsets(self) -> None:
        with pytest.raises(ValueError, match="precedes char_start"):
            self.make_chunk(char_start=200, char_end=100)

    @pytest.mark.parametrize(
        "bbox",
        [
            (-0.01, 0.1, 0.5, 0.6),
            (0.1, 0.1, 1.01, 0.6),
            (0.6, 0.1, 0.4, 0.6),
            (0.1, 0.6, 0.5, 0.4),
        ],
    )
    def test_rejects_invalid_normalized_bbox(self, bbox: tuple[float, float, float, float]) -> None:
        with pytest.raises(ValueError, match="normalized ordered rectangle"):
            self.make_chunk(bbox=bbox)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_rejects_non_finite_bbox_coordinates(self, bad: float) -> None:
        with pytest.raises(ValueError, match="must be finite"):
            self.make_chunk(bbox=(0.1, 0.2, bad, 0.4))

    def test_bbox_is_canonicalized_from_a_list(self) -> None:
        source = [0.1, 0.2, 0.3, 0.4]
        chunk = self.make_chunk(bbox=source)

        assert isinstance(chunk.bbox, tuple)
        source[0] = 0.99
        assert chunk.bbox == (0.1, 0.2, 0.3, 0.4)

    def test_is_immutable(self) -> None:
        chunk = self.make_chunk()

        with pytest.raises(FrozenInstanceError):
            chunk.page_number = 9  # type: ignore[misc]
