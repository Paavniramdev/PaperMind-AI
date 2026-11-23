PaperMind AI — Milestone 1 Architecture: Scientific PDF Ingestion & Document Understanding Engine
Version: 1.0.3 (M1 Design — OD-1 closed; M1.1 implemented + review corrections)
Status: M1.1 Implemented — Awaiting Final Review
Runtime Environment: Python 3.11.x | Node.js 24 LTS
Scope: Milestone 1 only
Primary Architect: Senior Software Architect
Date: November 2026

1. Purpose and Scope

1.1 Objective
M1 converts a raw scientific PDF into structured, provenance-carrying text that every later
milestone depends on. Concretely: validate the document, reconstruct the true reading order of
mixed single/two-column layouts, extract document-level metadata and section structure, and
produce structure-aware chunks that each carry an exact page-level origin.

M1 is the "Document Understanding Engine". If M1 is wrong, every downstream retrieval, ranking
and citation is built on corrupted text. Therefore M1 is measured and tested far more heavily
than it is written.

1.2 In Scope
- PDF integrity validation (magic bytes, size ceiling, corruption, encryption).
- Document-level scanned-document detection (not per-page).
- Layout-aware block extraction and reading-order reconstruction (vertical banding).
- Preservation of dual geometry: raw PDF points and normalized [0, 1] coordinates.
- Typography-assisted metadata extraction (title, authors) and section segmentation.
- Structure-aware chunking with page-level provenance and fixed overlap.
- Typed domain exceptions with a fixed mapping to future HTTP status codes.
- Comprehensive unit tests with programmatically generated PDF fixtures.

1.3 Out of Scope (explicit non-goals for M1)
- Embeddings, torch, sentence-transformers, numpy, FAISS, vector store  -> Milestone 2.
- Relational persistence (SQLAlchemy models, SQLite schema)             -> Milestone 2.
- FastAPI endpoints, streaming, frontend canvas viewer                  -> Milestone 3.
- RAG generation, citation verification, abstention                     -> Milestone 4.
- OCR of scanned documents (M1 only detects and rejects them)           -> future milestone.
- Table grid reconstruction, figure pixel analysis, LaTeX formula OCR   -> future milestone.

1.4 Architectural Boundary Rule
Everything under app/core/ MUST be framework-free and deterministic:
- No import of fastapi, starlette, or sqlalchemy anywhere in app/core/.
- Domain failures are typed Python exceptions; HTTP mapping happens only in the API layer.
- Public domain types are plain Python data structures; PyMuPDF types must not leak into them.
- Given identical input, every function returns identical output (UUIDs are injected, not
  generated internally by parsing logic).

2. Pipeline Architecture

    PDF bytes / Path
          |
          v
    [ validator ]   magic bytes -> size -> open -> encryption -> page count -> scanned?
          |         raises CorruptPDFException / FileTooLargeException /
          |                EncryptedPDFException / EmptyDocumentException /
          |                ScannedPDFException
          v
    ValidationReport + page-text statistics
          |
          v
    [ parser ]      per page: block extraction -> spanning-block detection ->
          |         vertical banding -> column sort -> reading order -> geometry
          v
    PageLayout[] (blocks in true reading order, dual geometry, column label)
          |
          v
    [ metadata + structure ]   title/author heuristics; section segmentation
          v
    Section[] (title, level, page range, char range)
          |
          v
    [ chunker ]     section-bounded, page-bounded, sentence-aware, overlapping
          v
    Chunk[] { chunk_id, paper_id, section_title, page_number, bbox,
              char_start, char_end, text }

Design note: the pipeline is a one-way chain of pure functions over immutable value objects.
Each stage can be tested in isolation by feeding it a hand-built upstream object.

3. Data Contracts

3.1 app/core/ingestion/models.py

- BlockGeometry
    Frozen. Holds raw PDF points (x0, y0, x1, y1) AND normalized coordinates
    (nx0, ny0, nx1, ny1) in [0, 1]. Both are kept so tests/debugging can use raw points while
    the frontend overlay and persistence use normalized values.

- LayoutBlock
    Frozen. Fields: order (reading-order index within its page), text, geometry, column
    ("left" | "right" | "spanning" | "single"), page_number (1-based).

- PageLayout
    Frozen. Fields: page_number (1-based), width, height, blocks (tuple of LayoutBlock),
    char_count, is_sparse.

- DocumentMetadata
    Frozen. Fields: title (str | None), authors (tuple[str, ...]), page_count, source_name.

  Cross-cutting invariants (all models above):
  - Finite numerics: every raw coordinate, normalized coordinate and page dimension must be
    finite; NaN, +inf and -inf are rejected with ValueError.
  - Deep immutability: tuple-typed collections (PageLayout.blocks, DocumentMetadata.authors)
    are canonicalized to tuples in __post_init__, so a mutable list handed to a constructor
    cannot later mutate an already-created model. The frozen, slotted dataclass contract is
    preserved.

3.2 app/core/chunking/models.py

- Chunk
    Frozen. Fields exactly as specified in SYSTEM_ARCHITECTURE.md section 2.2:
    chunk_id ("c_" + uuid4 hex), paper_id ("p_" + uuid4 hex), section_title, page_number,
    bbox (normalized [x0, y0, x1, y1]), char_start, char_end, text.
    Invariant (OD-1, closed): page_number and bbox describe exactly one page. A chunk never
    spans pages, so every chunk has exactly one unambiguous page origin.
    Offset invariant: char_start/char_end are half-open offsets into the parent section text
    that delimit a contiguous slice whose content is exactly `text`; therefore
    char_end - char_start == len(text) is enforced. A producer that normalizes the shipped text
    must keep the offsets consistent with that text (not with the raw parent string).
    Geometry is finite-checked, bbox is canonicalized to a tuple, and the same deep-immutability
    rule as the ingestion models applies.

3.3 ID conventions
    paper_id = "p_" + uuid4().hex ; chunk_id = "c_" + uuid4().hex.
    The prefix makes IDs self-describing in logs and JSON and prevents cross-type misuse.
    paper_id is supplied to the chunker by the caller (dependency injection) so that parsing
    and chunking remain fully deterministic and unit-testable.
    M1.1 boundary: validation produces no IDs at all; chunk_id generation belongs to M1.5.

3.4 app/core/ingestion/config.py  (M1.1)

- IngestionLimits
    Frozen, slotted, injectable value object holding every numeric limit the ingestion pipeline
    consumes, so no magic number is scattered through the validator:
    max_pdf_size_bytes, min_page_count, scanned_page_char_threshold, scanned_page_ratio,
    scanned_density_threshold. Invariants are validated on construction (ValueError).
    DEFAULT_INGESTION_LIMITS is the process-wide default; app/config.py adapts the same values
    from environment-overridable Settings via a read-only ingestion_limits property.
    Scope discipline: the D3 layout constants (span ratio, column split thresholds) are NOT
    defined here. They are measured in M1.2 and applied by the parser in M1.3, never by the
    validator.

3.5 app/core/ingestion/validator.py  (M1.1)

- ValidationReport
    Frozen, slotted, deterministic. Fields: source_name, page_count, page_char_counts
    (tuple[int, ...]), total_char_count, char_density, sparse_page_count, sparse_page_ratio,
    is_scanned. Holds only plain Python data; no PyMuPDF handle ever escapes the validator.
    Construction enforces internal consistency: per-page counts must be non-negative;
    page_count must equal len(page_char_counts); total_char_count must equal their sum;
    sparse_page_count must lie in [0, page_count]; char_density and sparse_page_ratio must
    match their derived values. build_validation_report rejects negative input the same way.
    The zero-page report is unchanged (page_count 0, density 0.0, not scanned). Because these
    are pure derivations, determinism is preserved.
- validate_pdf_bytes(data, *, source_name, limits) / validate_pdf_path(path, *, limits)
    Both return ValidationReport or raise one of the typed ingestion exceptions in the fixed
    order of section 2. Externally observable error precedence is identical across the two
    entry points: signature, then size, then open, encryption, page count, scanned detection.
    Memory trade-off: validate_pdf_path reads only the five-byte signature prefix before the
    stat-based size check, so an oversized file is never loaded into memory while a non-PDF
    file is still reported as corrupt (not oversized). The full file is read only after the
    ceiling passes; the signature/size checks inside validate_pdf_bytes then run redundantly,
    which is harmless and keeps a single implementation of the complete sequence.

4. Staged Execution Plan

Stage   Deliverable                                              Depends on
-----   -----------                                              ----------
M1.1    Ingestion foundation: pymupdf dependency, exceptions,    nothing
        models, validator, config limits, unit tests
M1.2    Layout reconnaissance (EXPERIMENT): arXiv benchmark      M1.1 + network
        fetch script + measurement probe over real PDFs
M1.3    Layout parser: parser.py + layout.py (banding, column    M1.2 measurements
        sort, reading order)
M1.4    Metadata + structure: metadata.py + structure.py         M1.3
        (title/authors, section segmentation)
M1.5    Structure-aware chunker: chunking/semantic.py            M1.4
M1.6    Hardening: >= 85% coverage on core/ingestion and         M1.5
        core/chunking, end-to-end integration test, decision log

Each stage follows the project cycle: Understand -> Experiment -> Measure -> Implement ->
Validate -> Explain -> Commit. No stage begins until the previous stage's acceptance criteria
are verified from real command output.

5. Engineering Decisions

D1  PyMuPDF selected as the sole extraction library.
    Rationale: one C-backed dependency provides block text with bounding boxes AND span-level
    font information (needed for heading detection), at high speed. pypdf has no layout;
    pdfplumber is slower and weaker at block segmentation; ML layout parsers are heavyweight
    black boxes that cannot be explained or measured.
    Trade-off: PyMuPDF is AGPL-3.0 (or commercial). Acceptable for this project; a licensing
    constraint if the product ever ships closed-source. Recorded, not blocking.
    Import note: use the modern name `import pymupdf` (the legacy alias `fitz` still resolves).

D2  Blocks for layout; "dict" spans for typography.
    Reading order operates on paragraph-like units from page.get_text("blocks"). Heading
    detection reads span font sizes from page.get_text("dict"). Word-level extraction is
    rejected as the primary granularity because it produces line-fragment noise.

D3  Vertical banding with centerline-based spanning detection.
    Naive ordering fails in two directions: pure y-sorting interleaves two-column text, and
    pure left/right splitting destroys full-width titles/abstracts. Banding resolves both:
    spanning blocks (title, abstract, wide tables) cut the page into horizontal bands; within
    each band, blocks are sorted left column then right column.
    This is the highest-risk component in M1. Its constants (span width > 0.70 * W, centerline
    x0 < 0.40 * W and x1 > 0.60 * W, column split x1 <= 0.55 * W / x0 >= 0.45 * W) are
    validated empirically in M1.2 against real papers, never assumed.

D4  Dual geometry: raw points and normalized coordinates.
    Normalized [0, 1] values drive the frontend highlight overlay at any zoom (M3).
    Raw points drive tests and debugging. Normalized values are what get persisted.

D5  Scanned detection is document-level, never per-page.
    A PDF is scanned if > 80% of its pages have < 50 extracted characters, OR overall density
    is < 100 characters per page. A single sparse page (cover page, full-page figure) must not
    reject an otherwise valid paper.
    Trade-off: a genuinely scanned PDF carrying OCR'd running headers could evade detection;
    accepted, and detection fails safe on the common case.

D6  Chunks never cross a section boundary, and never cross a page boundary. (Decided; closes OD-1)
    Section-bounding is mandated by the specification for semantic coherence. Page-bounding is
    the approved policy because Chunk carries exactly one page_number and one bbox, so each
    chunk must belong to exactly one page to keep citation provenance unambiguous. Rationale,
    trade-offs and closure are recorded in section 6.1. Cost: slightly smaller tail chunks at
    page ends, accepted in exchange for exact, verifiable provenance.

D7  Character budget with sentence snapping instead of a real tokenizer in M1.
    400 tokens is approximated as ~1600 characters (about 4 characters per token for English
    academic prose), with ~200 characters (about 50 tokens) of overlap. Importing
    transformers/tiktoken purely to count tokens would violate the M1 boundary, since ML
    libraries arrive in M2. The char-to-token ratio is measured in M1.2 and the budget is kept
    conservative so chunks stay safely inside the embedding model's 512-token window.

D8  Dependency-injected paper_id and prefixed UUIDs.
    The chunker receives paper_id rather than generating it, keeping parsing deterministic for
    tests. Prefixes ("p_", "c_") make IDs self-describing and misuse-resistant.

D9  Programmatic PDF fixtures rather than committed binaries.
    tests/fixtures/pdf_factory.py builds synthetic PDFs at test time (normal, two-page,
    sparse-page, all-sparse/scanned, empty, corrupt, invalid-magic, encrypted, oversized).
    Deterministic, diff-reviewable, and no binary blobs in git. Layout fixtures
    (two-column, spanning-abstract) are added in M1.3 when the parser needs them; M1.1 ships
    only the fixtures its validator actually exercises.

D10 Fail-fast typed exceptions with the domain layer kept HTTP-free.
    IngestionError base with CorruptPDFException (400), EmptyDocumentException (400),
    FileTooLargeException (413), EncryptedPDFException (422) and ScannedPDFException (422).
    Each carries an http_status attribute so the future API layer can map them without core
    importing FastAPI.
    FileTooLargeException (413) was added in M1.1 review: the file-size ceiling is a distinct
    class of client failure (request entity too large) rather than a corrupt-document fault,
    so it gets its own status instead of reusing the base 400 mapping. It is raised by both
    validate_pdf_bytes and validate_pdf_path, and each path has a dedicated test asserting the
    type, the 413 status and the human-readable MiB message.

D11 PyMuPDF is pinned below 2.x. (M1.1)
    pymupdf >= 1.24.0, < 2.0.0. PyMuPDF 2.x hard-requires numpy, onnxruntime, networkx,
    protobuf, flatbuffers, tabulate, psutil, pyyaml, pymupdf-layout and pymupdf4llm, which
    would violate the M1 non-negotiable "no ML dependencies". Resolved and installed version
    is 1.28.2, which ships py.typed coverage so strict mypy passes without suppressions.

6. Resolved Decisions

6.1 OD-1 — Page-boundary chunking policy (closes D6).  [STATUS: CLOSED — APPROVED, 2026-11-23]

    Decision:
      Option A. Chunks must never cross a page boundary. Every Chunk belongs to exactly one
      page and retains an unambiguous page_number and bbox. This is now a hard requirement,
      not a proposal.

    Rationale:
      - The Chunk contract (SYSTEM_ARCHITECTURE.md section 2.2) stores a single page_number and
        a single bbox. A chunk spanning two pages could not populate either field truthfully,
        so provenance would be ambiguous or outright false.
      - Verifiable citations are a core product promise. Retrieval must be able to point to the
        exact page and rectangle that produced an answer; page-bounded chunks make that a
        direct lookup rather than a heuristic reconstruction.
      - Page breaks are semantically strong boundaries in scientific papers. Concatenating the
        end of one page with the start of the next mixes content across a visual break.
      - It keeps the frontend highlight overlay (M3) trivial: one page, one rectangle, no merge
        logic and no multi-page coordinate reconciliation.

    Trade-offs accepted:
      - More, slightly shorter chunks. Every page contributes at least one chunk; page tails
        shorter than the target size are kept rather than merged forward, so total chunk count
        rises relative to cross-page packing.
      - Possible under-sized tail chunks. A page ending mid-sentence yields a small final chunk
        for that page. Mitigated by the fixed overlap (D7): the preceding context is still
        carried into the next page's first chunk, preserving cross-boundary retrieval recall
        without merging provenance.
      - Cannot amortise a page tail across the section. Accepted: unambiguous page provenance
        is valued above marginally more uniform chunk sizes.

    Rejected alternative:
      - Option B (cross-page chunks storing a page range and a merged bbox) reduces chunk count
        and yields more uniform sizes, but weakens citation precision to a page range and makes
        the bbox a union across two pages, which is not a truthful location for a single
        highlight overlay. Rejected on provenance-fidelity grounds.

    Effect on downstream stages:
      - M1.5 chunker enforces the page boundary in addition to the section boundary.
      - The M1.5 acceptance criterion "no chunk crosses a page boundary" is now a hard
        requirement rather than provisional.
      - M2 persistence stores exactly one page_number and one bbox per chunk row; this decision
        requires no schema change.

7. External Dependencies

- Runtime: pymupdf >= 1.24.0, < 2.0.0 (M1.1; see D11). Installed: 1.28.2.
  Imported as `import pymupdf`; the legacy `fitz` alias is not used.
- Dev: pytest-cov >= 5.0.0 (added in M1.1 for the coverage gate).
- Explicitly NOT added in M1: torch, sentence-transformers, faiss-cpu, numpy, langchain.
  Verified after install: pymupdf 1.28.2 pulls none of these transitively.

8. Benchmark Corpus

Source: public arXiv PDFs, fetched by a script in M1.2 and committed as a reproducible
benchmark set with a manifest recording arXiv ID, license, and retrieval date.
Target composition:
- Multiple two-column papers (IEEE/ACM-style, dense math).
- At least one single-column paper (arXiv preprint style).
- At least one paper with a spanning title/abstract over two-column body text.
- At least one scanned / image-only PDF (to exercise ScannedPDFException).
Purpose: tune D3 thresholds and the D7 char-to-token ratio from measured data, and produce
retrievable evidence for the portfolio (measured statistics, not opinions).

9. Acceptance Criteria

M1.1 Ingestion foundation  [IMPLEMENTED — review corrections applied]
- ruff check backend -> All checks passed.
- ruff format --check backend -> all files already formatted.
- mypy backend/app -> Success: no issues found (strict).
- pytest backend/tests -> all pass, including the 16 pre-existing M0 tests (no regressions).
- Each failure path raises its specific typed exception, proven by a dedicated test.
- A document with exactly one sparse page parses successfully (document-level detection proof).
- app/core/ingestion/* contains zero fastapi/sqlalchemy imports.
- No ML dependency added.
- Chunk contract enforces char_end - char_start == len(text).
- Domain models reject non-finite numerics and canonicalize tuple-typed collections, so a
  mutable list input cannot mutate a created model.
- ValidationReport rejects inconsistent statistics; build_validation_report rejects negative
  per-page counts.
- validate_pdf_bytes and validate_pdf_path report the same exception for the same defective
  input (signature before size), without reading an oversized file into memory.

M1.2 Layout reconnaissance
- Benchmark corpus fetched and committed with a manifest.
- A measurement report exists (per-page block counts, width distributions, spanning fraction,
  font-size ranges, char-to-token ratio) that justifies or revises every D3/D7 constant.

M1.3 Layout parser
- Reading Order Assertion: for a two-column fixture, all left-column text precedes all
  right-column text with zero interleaving.
- Mixed Layout Assertion: full-width title/abstract precede two-column body text.
- Coordinate Preservation: every block has valid normalized coordinates in [0, 1].

M1.4 Metadata + structure
- Title and section headings detected on fixtures; section list is ordered and non-overlapping.
- Sparse Page Tolerance: a valid document containing a sparse page parses without raising.

M1.5 Chunker
- No chunk crosses a section boundary; no chunk crosses a page boundary (OD-1, closed: hard
  requirement). Every chunk asserts exactly one page_number and one bbox covering that page.
- Overlap is present and bounded; char offsets are internally consistent with the text.
- Determinism: identical input yields identical chunk boundaries and offsets.

M1.6 Hardening
- > 85% line coverage across app/core/ingestion and app/core/chunking.
- One end-to-end test: PDF bytes -> validated -> parsed -> chunked, asserting provenance.
- Decision log entries recorded for D1-D11 (final values after measurement).
