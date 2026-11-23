PaperMind AI — Architectural Decision Log (ADR)
Version: 2.3.7
Status: Approved Greenfield Architecture
Runtime Environment: Python 3.11.x | Node.js 20 LTS
Deployment Model (MVP): Single-Worker Uvicorn Process (workers = 1)
Date: November 2026
Index of Architectural Decisions
- DEC-001: Embedding Model Selection
- DEC-002: Relational Database & Migration Strategy
- DEC-003: Single Global FAISS Vector Index
- DEC-004: PDF Parsing, Layout Banding & Scanned Detection
- DEC-005: Handling Complex Document Elements
- DEC-006: Buffered RAG & Verification Semantics
- DEC-007: Frontend/Backend Streaming Transport
- DEC-008: Evaluation Hardware & Measured Benchmark Targets
- DEC-009: Runtime Versions & Authoritative Path Resolution
- DEC-010: MVP Scope & Feature Boundaries
- DEC-011: Staged Dependency Installation Lifecycle
- DEC-012: Paper-Level Filtering via FAISS IDSelectorBatch
- DEC-013: SQLite Embedding BLOB Persistence & Zero-Compute Recovery
- DEC-014: Configurable Abstention Threshold & Empirical Validation
- DEC-015: Explicit ID Semantics, Lock-Before-Mutation & Single-Worker Concurrency
- DEC-016: Deterministic 10-Step Mutation & Publication Protocol, Search Consistency, Paper Eligibility & Crash Recovery
  DEC-001: Embedding Model Selection
- Status: Finalized
- Decision: Select BAAI/bge-small-en-v1.5 as the sole initial embedding model.
- Specification: 384 dimensions; 133 MB footprint; strict L2 normalization ($||\vec{v}||_2 = 1.0$); asymmetric query prefix "Represent this sentence for searching relevant passages: ". Document chunks are encoded directly without instruction.
- Rationale: Minimal footprint, fast CPU inference (~12ms per chunk), allowing ingestion of a 15-page paper in $< 1.0\text{ s}$ without a GPU.
  DEC-002: Relational Database & Migration Strategy
- Status: Finalized
- Decision: Use SQLite 3 running with Write-Ahead Logging (WAL) via SQLAlchemy 2.0 for the MVP.
- PostgreSQL Migration Reality:
  - Acknowledged that migrating to PostgreSQL in a future multi-tenant release is not merely changing a connection string. It requires:
    1. Database schema migration scripts via Alembic.
    2. Dialect validation (PostgreSQL native UUID, JSONB, and BYTEA data types).
    3. Connection pool sizing (QueuePool).
    4. Foreign key index optimization for concurrent transactions.
       DEC-003: Single Global FAISS Vector Index
- Status: Finalized
- Decision: Implement one single global FAISS IndexFlatIP for the user's research library.
- Specification: Published via immutable generation artifacts referenced by data/vector_indices/manifest.json.
- Threshold for Alternative Index (IndexHNSWFlat): An approximate graph index (IndexHNSWFlat) will be considered only when the global library exceeds $100{,}000$ chunks and sub-linear search time is required.
  DEC-004: PDF Parsing, Layout Banding & Scanned Detection
- Status: Finalized
- Decision: Use PyMuPDF (fitz) with vertical layout banding and document-level scanned detection.
- Specification:
  - Full-Width Spanning Blocks: Classified when $(x_1 - x_0) > 0.70 \times W$ or spanning the centerline ($x_0 < 0.40 \times W$ and $x_1 > 0.60 \times W$).
  - Vertical Banding: Spanning blocks divide the page vertically into bands. Two-column text between spanning blocks is partitioned by $x$-midpoint and sorted: Left Column top-to-bottom ($y_0$), then Right Column top-to-bottom ($y_0$).
  - Document-Level Scanned Detection: Rejection occurs only if $> 80%$ of pages have $< 50$ text characters or document character density is $< 100$ chars/page. Individual sparse pages (cover pages, diagrams) do not cause document rejection.
  - Structured Failure Reporting: Domain exceptions (CorruptPDFException, EncryptedPDFException, ScannedPDFException, EmptyDocumentException) map to clear HTTP error codes and user messages.
    DEC-005: Handling Complex Document Elements
- Status: Finalized
- Decision: Explicitly define element handling for MVP vs. Post-MVP:
  - Multi-column & mixed layouts: Fully supported via vertical banding and column sorting.
  - Tables: Extracted as contiguous text blocks within their section chunk. Complex table structure reconstruction is deferred.
  - Figures: Raster image pixels are ignored; figure captions are extracted as text.
  - Math Expressions: Preserved as extracted Unicode text. Complex LaTeX OCR formula reconstruction is deferred.
  - Scanned PDFs: Explicitly rejected at the document level with a clean user-facing error message. OCR fallback is scheduled for Milestone 6.
    DEC-006: Buffered RAG & Verification Semantics
- Status: Finalized
- Decision: Buffer LLM generations server-side before client delivery to execute citation integrity and grounding checks.
- Explicit Verification States:
  - VERIFIED: All citation IDs are valid ($1 \le N \le k$), every factual sentence has a citation, and all cited sentences passed lexical/entity overlap sanity checks against the source chunk text.
  - PARTIAL_WARNING: Citation IDs are valid, but one or more cited sentences failed the lexical/entity overlap check (or an assertion lacked a citation).
  - ABSTENTION: Maximum retrieval similarity is below RETRIEVAL_ABSTENTION_THRESHOLD or model indicates lack of evidence.
- Heuristic Boundary: Lexical/entity overlap is a heuristic sanity check; it does NOT prove semantic correctness, logical validity, or factual truth.
  DEC-007: Frontend/Backend Streaming Transport
- Status: Finalized
- Decision: Use Server-Sent Events (SSE) over standard HTTP/1.1 (text/event-stream).
- Specification: Endpoint POST /api/v1/query/stream emitting events: context, verification, token, warning, done, and error.
  DEC-008: Evaluation Hardware & Measured Benchmark Targets
- Status: Finalized
- Decision: Define a baseline hardware environment and enforce realistic, measured benchmark targets.
- Specified Environment: Standard developer machine: 8-core CPU (Intel/AMD/Apple Silicon), 16 GB RAM, no GPU required (pure CPU execution), single Uvicorn worker process.
- Benchmark Goals:
  - Ingestion: Measured benchmark target $< 5.0\text{ s}$ (stretch $< 3.5\text{ s}$) for a 15-page PDF.
  - FAISS Search: Measured benchmark target $< 15\text{ ms}$ (stretch $< 8\text{ ms}$) over evaluated scope of 10,000 chunks (scaling to 50,000 chunks requires separate benchmarking).
  - Index Recovery: Measured benchmark target $< 100\text{ ms}$ (stretch $< 50\text{ ms}$) for 10,000 chunks from SQLite BLOBs.
  - Memory Footprint: Measured benchmark target $< 1.5\text{ GB}$ (stretch $< 1.0\text{ GB}$) backend RSS.
  - Note: Performance metrics are treated as measured benchmark targets, not guaranteed minimums.
    DEC-009: Runtime Versions & Authoritative Path Resolution
- Status: Finalized
- Decision: Lock runtimes to Python 3.11.x and Node.js 20 LTS (Iron).
- Authoritative Dynamic Path Resolution:
  - Both PAPERMIND_DATA_DIR and DATABASE_URL anchor to module-level REPO_ROOT = Path(file).resolve().parent.parent.parent directly in config.py.
  - Relative paths are resolved against module-level REPO_ROOT, guaranteeing identical file resolution whether executed from the project root, backend/, or test runners.
    DEC-010: MVP Scope & Feature Boundaries
- Status: Finalized
- Decision: Establish an immutable scope boundary for the MVP.
- MVP Includes: PDF upload, layout-aware PyMuPDF extraction, structure-aware chunking, BGE-small embeddings, single global FAISS IndexFlatIP vector search with IDSelector filtering, manifest-based crash-safe publication, buffered grounded RAG Q&A, citation verification, and split-screen React reader with citation navigation.
- Post-MVP Includes: BM25 hybrid search, Cross-Encoder re-ranking, multi-paper synthesis, OCR fallback, and Docker production containerization.
  DEC-011: Staged Dependency Installation Lifecycle
- Status: Finalized
- Decision: Decouple dependency installation by milestone to ensure lightweight scaffolding:
  - Milestone 0: FastAPI, Pydantic, Pydantic Settings, SQLAlchemy, Pytest, HTTPX, Ruff, Mypy; React, Vite, Tailwind, ESLint. (Zero PyTorch/FAISS).
  - Milestone 1: PyMuPDF.
  - Milestone 2: Sentence Transformers, PyTorch, FAISS CPU, NumPy.
  - Milestone 4: LangChain Core and LLM provider integrations.
    DEC-012: Paper-Level Filtering via FAISS IDSelectorBatch
- Status: Finalized
- Decision: Reject candidate oversampling ($5 \times k$) with post-filtering; implement FAISS native IDSelectorBatch.
- Complexity Reality:
  - IDSelectorBatch restricts result eligibility strictly to the target paper.
  - In IndexFlatIP, distance evaluation scans all $N$ library vectors with $O(N \cdot d)$ complexity plus an $O(1)$ selector lookup per candidate.
  - Retained for MVP because $O(N \cdot d)$ satisfies the $< 15\text{ ms}$ search target for the 10,000 chunks evaluated scope on modern CPUs.
    DEC-013: SQLite Embedding BLOB Persistence & Zero-Compute Recovery
- Status: Finalized
- Decision: Store raw float32 vector bytes in SQLite chunks.embedding alongside chunk metadata.
- Specification: Raw binary BLOB (1,536 bytes/chunk).
- Rationale: Enables rebuild_index_from_db() to reconstruct library_{gen}.faiss in measured benchmark target $< 100\text{ ms}$ (stretch $< 50\text{ ms}$) on CPU without recomputing embeddings.
  DEC-014: Configurable Abstention Threshold & Empirical Validation
- Status: Finalized
- Decision: Convert retrieval similarity threshold to a configurable parameter: RETRIEVAL_ABSTENTION_THRESHOLD: float = 0.40.
- Validation Procedure: Evaluated in Milestone 4 across 10 supported and 10 unsupported questions to measure false abstentions and false answers, tuning the threshold based on empirical precision/recall data.
  DEC-015: Explicit ID Semantics, Lock-Before-Mutation & Single-Worker Concurrency
- Status: Finalized
- Decision: Distinguish persistent chunk identity from generation-specific vector positions, mandate that the process-wide exclusive lock is acquired before starting any SQLite mutation, and restrict MVP concurrency model to a single Uvicorn worker.
- Specification:
  - chunk_id (UUID4) is the permanent, immutable identity.
  - faiss_id (integer) is a generation-specific vector position (0..N-1), not a permanent identity. Every MVP index-changing operation rebuilds the complete eligible generation and reassigns contiguous positions; append-in-place is not used.
  - Lock-Before-Mutation: The process-wide exclusive lock (threading.Lock) must be acquired before starting any SQLite transaction that mutates the indexed chunk set (ingestion, deletion, rebuild).
  - The lock remains held continuously throughout database mutation, atomic invalidation (index_generation = NULL), index rebuild, SQLite generation commit, manifest publication, disk validation, and active snapshot replacement.
  - The MVP deployment runs strictly as a single Uvicorn worker process (workers = 1). Process-local threading.Lock serializes write operations and coordinates search requests. Multi-worker/cross-process locking is deferred to post-MVP.
    DEC-016: Deterministic 10-Step Mutation & Publication Protocol, Search Consistency, Paper Eligibility & Crash Recovery
- Status: Finalized
- Decision: Standardize on a deterministic 10-step mutation and publication sequence coupled with pre-mutation locking, in-transaction SQLite invalidation, candidate-aware paper eligibility, exact generation membership, one deterministic search-locking contract, post-commit compensation, and 6-point startup integrity validation.
- Full-generation rebuild rule: Every MVP ingestion, deletion, and recovery operation builds a complete new generation from the eligible SQLite chunk set; no append-in-place operation is permitted. Assign contiguous generation-specific faiss_id values 0..N-1 in deterministic (paper_id, chunk_index) order.
- Candidate eligibility rule:
  - For ingestion, the candidate generation includes all existing ACTIVE papers plus the single explicitly identified candidate_paper_id for the current ingestion operation, provided its complete chunk set and embedding BLOBs have been validated and committed.
  - The candidate paper remains PROCESSING until publication, snapshot activation, and its final status transaction succeed.
  - All unrelated PROCESSING papers and all FAILED papers are excluded.
  - For deletion and startup recovery, candidate generation membership is ACTIVE papers only.
- Specification:
  1. Acquire exclusive lock (threading.Lock) before opening any database transaction.
  2. Execute the SQLite mutation and atomic generation invalidation (index_generation = NULL) in one transaction; detach the in-memory snapshot.
  3. Read eligible chunks: for ingestion, existing ACTIVE papers plus only the validated current candidate_paper_id; for deletion/recovery, ACTIVE papers only.
  4. Assign contiguous generation-specific faiss_ids (0..N-1) and build IndexFlatIP plus the exact mapping registry.
  5. Generate gen_uuid = uuid4().hex.
  6. Write immutable generation artifacts (library_{gen}.faiss, mapping_{gen}.json).
  7. Validate artifacts on disk (existence, size $> 0$, loadable index, vector count, and mapping integrity).
  8. In one SQLite transaction, set faiss_id = NULL for chunks outside the candidate generation, assign contiguous IDs to its exact members, and commit index_generation = gen_uuid (candidate paper remains PROCESSING).
  9. Publish manifest.json atomically via os.replace.
  10. Re-read and validate the manifest, swap the active IndexSnapshot, commit the ingestion candidate's status to ACTIVE, and release the lock only after all operations succeed.
- One Deterministic Search-Locking Contract:
  - Every search acquires the same process-wide threading.Lock used by writers and holds it for the entire operation: snapshot acquisition, FAISS search, mapping resolution, and SQLite chunk hydration.
  - Writers hold the lock from before any indexed-chunk SQLite mutation through publication, snapshot replacement, and compensation.
  - If no valid snapshot is available after acquiring the lock (self._snapshot is None), search returns HTTP 503 ServiceUnavailableException.
  - All blocking vector-store operations execute in worker threads via asyncio.to_thread(...).
- Post-Commit Failure Compensation:
  - Failures before Step 8 leave index_generation = NULL; ingestion candidate is marked FAILED, its faiss_ids are cleared, and snapshot remains None.
  - Failures after Step 8 execute a compensating transaction setting index_generation = NULL, clearing candidate faiss_ids, and marking the candidate FAILED; snapshot remains None.
  - If compensation fails, log critically, keep snapshot None, release the lock safely in finally, and require startup recovery.
- Startup Recovery & 6-Point Startup Validation:
  - Phase 1: in one SQLite transaction, mark every interrupted PROCESSING paper FAILED, clear its chunk faiss_ids, and set index_generation = NULL. Retain paper/chunk records.
  - Phase 2: (1) exact expected eligible chunk_id set equals mapping membership; (2) generation-member IDs are unique and contiguous 0..N-1, nonmembers have faiss_id = NULL; (3) registry count $N$; (4) exact mapping-to-SQLite consistency; (5) FAISS vector count $N$; (6) unified non-NULL generation UUID.
  - Startup rebuilds from ACTIVE papers only whenever Phase 1 changed status or any integrity check fails. No queries are accepted until recovery completes.
  - Startup integrity validation is the authoritative MVP recovery mechanism; an administrative rebuild API is not required for MVP.