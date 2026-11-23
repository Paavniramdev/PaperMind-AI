PaperMind AI — Architecture Changelog & Technical Revisions
Version: 2.3.7
Date: November 2026
Status: Approved Greenfield Specification
[2.3.8] — Milestone 0 Runtime Documentation Correction
- Runtime Pin Corrected: The frontend runtime requirement was updated from Node.js 20 LTS (Iron) to Node.js 24 LTS across the specification documents, aligning the written specification with the verified host toolchain (Node.js v24.18.0, npm 11.16.0).
- Rationale: The Milestone 0 environment runs Node.js 24 LTS. Vite, ESLint 9 flat config, TypeScript strict mode, and the frontend lint/build scripts were validated successfully under Node.js 24. No architectural decision other than the runtime pin was affected.
- Scope: Documentation text only. This revision does not change Milestone 0 application code, dependency sets, or acceptance criteria.
[2.3.7] — Ingestion Eligibility, Generation Membership & Startup Recovery Consistency
1. Newly Ingested Paper Included in Its First Published Generation
   - A newly ingested paper remains PROCESSING until publication succeeds, but is included in that ingestion operation's candidate generation after its complete chunk set and embedding BLOBs have been validated and committed.
   - Candidate eligibility is all existing ACTIVE papers plus only the explicitly identified candidate_paper_id for the current ingestion operation. Unrelated PROCESSING and all FAILED papers are excluded.
   - The paper becomes ACTIVE only after manifest validation, in-memory snapshot activation, and a successful final status transaction, all while the exclusive lock remains held.
   - If activation fails after snapshot swap, detach the snapshot and compensate before releasing the lock.
2. Exact Generation Membership & Stale ID Prevention
   - The mapping registry's exact persistent chunk_id set defines generation membership; numeric faiss_id range checks alone are insufficient.
   - During generation commit, set faiss_id = NULL for chunks outside the generation and assign contiguous 0..N-1 positions only to generation members.
   - Startup validation compares the expected eligible chunk-ID set with the registry and validates every mapping against SQLite.
3. Interrupted Ingestion Recovery
   - If startup finds PROCESSING papers, it marks them FAILED, clears their chunk faiss_id values, and invalidates library_metadata.index_generation in the same SQLite transaction.
   - Startup then rebuilds from ACTIVE papers only before accepting searches. This closes the crash window after manifest publication or snapshot activation but before the final ACTIVE status commit.
4. Acceptance-Test Alignment
   - Milestone 2 tests distinguish the current ingestion candidate from unrelated PROCESSING papers.
   - Tests prove a successful new upload is searchable immediately after its first publication; unrelated PROCESSING and all FAILED papers remain excluded.
     [2.3.5] — Startup Recovery, ACTIVE-Paper Eligibility & Unified Search-Locking Contract
5. Startup Recovery & ACTIVE-Paper Indexing Eligibility
   - Rule Established: Only chunks belonging to papers with status = 'ACTIVE' may enter a published, searchable FAISS generation. Chunks of PROCESSING or FAILED papers are never included in any rebuilt index.
   - Step 3 Corrected: The 10-step protocol Step 3 now selects only ACTIVE-paper chunks via a JOIN papers … WHERE papers.status = 'ACTIVE' filter instead of an unfiltered table scan.
   - Startup Phase 1 — PROCESSING Paper Recovery: On startup, before index integrity checks, the system scans for papers left in status = 'PROCESSING' by an unhandled crash and transitions them to FAILED. Chunk records are retained (not deleted) for auditability. No new recovery subsystem is introduced.
   - 6-Point Startup Validation: The previously named 5-point validation is expanded to 6 points, adding an explicit paper-eligibility check as point 1: confirms that no non-ACTIVE-paper chunk appears in the current generation's faiss_id range. Subsequent checks (contiguous IDs, registry count, mapping consistency, FAISS vector count, unified generation UUID) are renumbered 2–6.
   - Consistency Preserved: Deletion and ingestion recovery continue to use the same generation-invalidation and post-commit compensation invariants established in v2.3.3–v2.3.4.
6. Unified Search-Locking Contract & Documentation Consistency
   - One Contract, All Documents: Ambiguous wording such as "either wait for the lock or return 503" has been removed from all eight documents. The single deterministic search-locking contract now reads consistently:
     - Every search acquires the same process-wide threading.Lock used by writers and holds it for the entire operation (snapshot acquisition, FAISS search, mapping resolution, SQLite chunk hydration).
     - Writers acquire the same lock before any indexed-chunk SQLite mutation and hold it through publication, snapshot replacement, and any compensation.
     - If no valid snapshot is available after acquiring the lock, search returns HTTP 503 immediately.
     - All blocking operations execute in worker threads via asyncio.to_thread(...), keeping the asyncio event loop unblocked.
   - Administrative Rebuild Endpoint Clarification: References to an optional administrative rebuild API endpoint (POST /api/v1/admin/rebuild-index) have been removed from requirement and changelog text. Startup integrity recovery (Phase 1 + 6-point check) is the authoritative MVP recovery mechanism. Administrative endpoints are not required for MVP delivery.
     [2.3.3] — Lock Lifecycle & Search Consistency Hardening
7. Lock-Before-Mutation Mandate
   - Vulnerability Closed: In v2.3.2, the exclusive index lock was acquired at the beginning of the publication protocol, but SQLite mutations (ingestion chunk inserts, deletion row removals) occurred before that protocol began. This left a window where concurrent search requests could read mutated SQLite records while querying the old in-memory FAISS index.
   - Correction: The process-wide exclusive index lock (threading.Lock) must be acquired before starting any SQLite transaction that mutates the indexed chunk set. The lock remains continuously held across database mutation, generation invalidation, index rebuild, SQLite generation commit, manifest publication, disk validation, and active in-memory snapshot replacement.
8. Atomic Mutation and Generation Invalidation
   - In the exact same SQLite transaction as row deletion or chunk insertion, library_metadata.index_generation is explicitly set to NULL:UPDATE library_metadata SET index_generation = NULL WHERE key = 'index_generation';
   - This transaction is committed before index rebuilding begins.
   - Simultaneously, the active in-memory snapshot is detached (self._snapshot = None).
   - Guarantees that a partially ingested or deleted state is never associated with a valid generation UUID, either in SQLite or in memory.
9. Search Consistency & Concurrency Coordination
   - The in-memory active index state is managed as an immutable IndexSnapshot reference (index, mapping, reverse_mapping, generation, chunk_count).
   - Because the exclusive lock is acquired before SQLite mutation starts and the active snapshot is detached upon invalidation, a search request never evaluates an old FAISS index against a newly mutated database.
   - Search requests acquire the same lock used by writers and hold it through snapshot acquisition, FAISS search, mapping resolution, and SQLite chunk hydration. If no valid snapshot is available after acquiring the lock, search returns HTTP 503.
   - Database chunk hydration strictly queries persistent chunk_ids from the active snapshot.
10. Robust Failure Handling & Automatic Recovery
    - If an exception occurs at any point during rebuild, disk write, validation, or manifest publication:
      - Pending transactions are rolled back; committed mutations leave SQLite index_generation = NULL.
      - In-memory active_snapshot remains None.
      - The exclusive lock is released in a finally block to prevent process deadlock.
      - Search requests cleanly return HTTP 503 ServiceUnavailableException until startup integrity recovery re-synchronizes the index.
11. Deterministic 10-Step Mutation & Publication Protocol
    - Unified the publication lifecycle into a complete 10-step sequence:
      1. Acquire exclusive lock (threading.Lock) before opening any database transaction.
      2. Execute SQLite mutation & atomic invalidation (index_generation = NULL); detach active_snapshot = None.
      3. Read authoritative SQLite chunk records and embedding BLOBs.
      4. Assign contiguous faiss_ids (0..N-1) and build structures.
      5. Generate new gen_uuid.
      6. Write immutable generation artifacts (library_{gen}.faiss, mapping_{gen}.json).
      7. Validate artifacts on disk.
      8. Commit new faiss_ids and library_metadata.index_generation = gen_uuid in SQLite.
      9. Publish manifest.json atomically via os.replace.
      10. Validate published generation, swap active IndexSnapshot pointer, and release lock.
          [2.3.2] — Final Persistence Protocol & Crash Recovery Hardening
12. Deterministic 9-Step Index Publication Sequence
    - Gap Resolved: The exact ordering between SQLite generation metadata updates and filesystem manifest publication was previously undefined.
    - Protocol Formally Defined:
      1. Acquire exclusive process-wide index lock (threading.Lock).
      2. Read authoritative SQLite chunk records and embedding BLOBs.
      3. Reassign contiguous generation-specific faiss_ids (0..N-1) and build in-memory IndexFlatIP and mapping registry.
      4. Generate new generation UUID (gen_uuid).
      5. Write immutable generation-specific artifacts (library_{gen_uuid}.faiss, mapping_{gen_uuid}.json).
      6. Validate both artifacts before publication (existence, size $> 0$, loadability, vector count).
      7. In one SQLite transaction, persist new faiss_id assignments and commit library_metadata.index_generation = gen_uuid.
      8. Publish manifest.json using temporary file and atomic os.replace.
      9. Validate published generation before releasing the lock and accepting search queries.
13. Comprehensive Interruption-Point Crash Recovery
    - Interruption Behavior Documented:
      - Crash before SQLite generation commit: SQLite rolls back. If generation was invalidated, SQLite holds index_generation = NULL, which mismatches manifest.json, triggering automatic rebuild on startup.
      - Crash after SQLite commit but before manifest publication: SQLite committed gen_uuid_new, but filesystem manifest has gen_uuid_old. Startup detects generation mismatch and rebuilds.
      - Crash during manifest replacement: Atomic os.replace guarantees filesystem reads either the complete old or complete new manifest. Validated against SQLite; any mismatch triggers rebuild.
      - Crash after successful publication: Validated and loaded cleanly.
      - Core Invariant: The system never serves queries using a mismatched or unverified generation.
14. Strengthened 5-Point Startup Integrity Validation
    - Replaced basic count checks with comprehensive integrity validation:
      1. Contiguous IDs: SQLite faiss_id values are unique and strictly contiguous from 0 through N-1.
      2. Registry Count: Mapping registry contains exactly $N$ entries.
      3. Exact Mapping Consistency: Every registry entry maps to the correct persistent SQLite chunk_id and faiss_id.
      4. Vector Count Integrity: FAISS index contains exactly $N$ vectors (index.ntotal == N).
      5. Unified Generation Match: Manifest, SQLite metadata, mapping registry, and FAISS filename tag all identify the exact same generation UUID.
15. Index-Changing Mutation Coverage
    - Both paper ingestion and paper deletion atomically invalidate library_metadata.index_generation = NULL in their SQLite transaction before building the new generation.
    - Guarantees that a crash after a database mutation can never allow a stale index to be accepted, even if old and new chunk counts happen to match.
      [2.3.1] — Critical Corrections & Publication Hardening
    - Fixed module-level REPO_ROOT reference in config.py properties.
    - Replaced dual os.replace with generation-based immutable artifacts and atomic manifest.json.
    - Closed deletion crash window via in-transaction SQLite generation invalidation.
    - Defined distinct semantics: chunk_id (permanent UUID) vs faiss_id (generation-specific position).
    - Explicitly scoped MVP concurrency to a single Uvicorn worker process (workers = 1).
    - Aligned $< 15\text{ ms}$ search target strictly to the evaluated 10,000 chunks scope.
      [2.3.0] — Technical Revisions
    - Added FAISS IDSelectorBatch complexity analysis ($O(Nd)$ scan reality).
    - Historical v2.3.0 policy: stable FAISS ID append and rebuild-on-delete. Superseded for the MVP by v2.3.7's full-generation rebuild policy.
    - Implemented working-directory-independent configuration for both data dir and DB URL.
    - Unified recovery target to $< 100\text{ ms}$ (stretch $< 50\text{ ms}$).
    - Refined verification language distinguishing citation integrity from semantic correctness.
      [2.2.0] — Architecture Consistency Revisions
    - Replaced candidate oversampling with IDSelectorBatch filtering.
    - Implemented SQLite embedding BLOB persistence for zero-compute recovery.
    - Defined discrete verification states: VERIFIED, PARTIAL_WARNING, ABSTENTION.
    - Added configurable RETRIEVAL_ABSTENTION_THRESHOLD (0.40) and calibration procedure.