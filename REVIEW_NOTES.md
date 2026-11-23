PaperMind AI v2.3.6 — Mentor Review Notes
What changed
1. Fixed the ingestion eligibility contradiction: the current validated ingestion candidate is included in its first FAISS generation while it remains PROCESSING; unrelated PROCESSING and all FAILED papers remain excluded.
2. Defined generation membership by the exact set of persistent chunk_id values in the mapping registry, rather than by numeric faiss_id range alone.
3. Made faiss_id nullable for chunks outside the active generation. Generation publication clears nonmember IDs and assigns contiguous IDs only to generation members.
4. Kept PDF parsing and embedding computation outside the global index lock; the lock is acquired before indexed SQLite mutations and held through publication and compensation.
5. Strengthened Step 10: manifest validation, snapshot activation, and the final candidate ACTIVE status transaction all occur while the writer lock is held. The lock is released only after the status transaction commits.
6. Strengthened failure compensation to detach the snapshot, invalidate the generation, clear candidate faiss_id values, and mark the candidate FAILED where possible.
7. Strengthened startup recovery: interrupted PROCESSING papers are marked FAILED, their faiss_id values are cleared, and index_generation is invalidated in the same transaction. Startup then rebuilds from ACTIVE papers only.
8. Updated Milestone 2 acceptance tests to prove that a successfully uploaded paper is searchable immediately after its first publication.
9. Made the Milestone 0 approval gate explicit. The documents do not authorize implementation.
Current project state
- Documentation revision: 2.3.6
- Documents revised: 8/8
- Milestone 0: Not started; explicit user approval still required
- Application code: Not started
- No tests or runtime commands have been executed as part of this documentation revision.
Important implementation constraint
The 10-step protocol is an architectural specification. During M2 implementation, the code and tests must enforce the exact candidate ID passed by the ingestion operation; never implement the candidate exception as a broad status = 'PROCESSING' inclusion rule.