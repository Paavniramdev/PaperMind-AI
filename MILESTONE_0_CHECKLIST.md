PaperMind AI — Milestone 0 Checklist: Scaffolding & Tooling
Version: 2.3.7
Status: Authorized to Begin (User Approval Received 2026-11-23)
Objective: Establish the clean monorepo structure, development environment, tooling, and test pipelines without installing heavy AI/ML libraries or implementing application code.
1. Prerequisites Verification
   Before starting Milestone 0, verify that the host system meets the required runtimes:
Verify Python version (Must be 3.11.x)
python --version
Verify Node.js version (Must be 24.x LTS)
node --version
Verify npm version (Must be >= 11.x)
npm --version
Verify Git is available
git --version
2. Milestone 0 Task Checklist
Phase 0.1: Directory Hierarchy Setup
- [x] Create root directory structure:
  - backend/app/{api/v1/endpoints,core/{ingestion,chunking,embeddings,vector_store,rag},db,schemas}
  - backend/tests/{unit,integration,fixtures}
  - frontend/src/{components/{layout,reader,chat,upload},hooks,services,types}
  - data/{raw_papers,vector_indices}
  - docs/
    Phase 0.2: Backend Tooling & Lightweight Dependency Configuration
- [x] Create backend/pyproject.toml specifying only M0 dependencies (no PyTorch, Sentence Transformers, or FAISS):
  - Core dependencies: fastapi>=0.111.0, uvicorn>=0.30.0, pydantic>=2.7.0, pydantic-settings>=2.2.0, sqlalchemy>=2.0.0.
  - Development dependencies: pytest>=8.2.0, pytest-asyncio>=0.23.0, httpx>=0.27.0, ruff>=0.4.0, mypy>=1.10.0.
  - Tool configurations:
    - Ruff: Target Python 3.11, line length 100, linting rules (E, F, I, B, UP).
    - Mypy: Strict mode enabled, disallow_untyped_defs = true.
    - Pytest: asyncio_mode = "auto".
- [x] Create backend/app/config.py with authoritative working-directory-independent path resolution for both PAPERMIND_DATA_DIR and DATABASE_URL referencing module-level REPO_ROOT = Path(file).resolve().parent.parent.parent directly.
- [x] Create backend/app/main.py minimal health-check application (GET /health).
- [x] Create .env.example in repository root with required schema (OPENAI_API_KEY= left empty).
- [x] Create root .gitignore covering Python bytecode, .venv/, Node node_modules/, dist/, OS artifacts, and local data/ storage.
  Phase 0.3: Frontend Tooling & Skeleton Configuration
- [x] Initialize frontend/package.json with dependencies:
  - Dependencies: react, react-dom, lucide-react.
  - Dev dependencies: vite, @vitejs/plugin-react, typescript, @types/react, @types/react-dom, tailwindcss, postcss, autoprefixer, eslint, @typescript-eslint/parser, @typescript-eslint/eslint-plugin.
  - Scripts:
    - "dev": "vite"
    - "build": "tsc && vite build"
    - "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0"
    - "preview": "vite preview"
- [x] Configure frontend/vite.config.ts with API proxy mapping /api to http://localhost:8000.
- [x] Configure frontend/tsconfig.json with strict TypeScript compilation.
- [x] Configure frontend/tailwind.config.js and frontend/src/index.css.
- [x] Create minimal frontend/src/App.tsx displaying the PaperMind AI system status.
  Phase 0.4: Test Harness & Verification Scripts
- [x] Create backend/tests/conftest.py with httpx.AsyncClient test fixture against app.
- [x] Create backend/tests/unit/test_sanity.py testing health endpoint and environment loading.
- [x] Create backend/tests/unit/test_config.py asserting that path normalization resolves identical absolute paths across:
  1. Default configuration.
  2. Relative DATABASE_URL override.
  3. Relative PAPERMIND_DATA_DIR with DATABASE_URL unset.
  4. Explicit absolute database paths.
  5. Execution from repository root and backend/ directory.
3. Milestone 0 Verification Commands & Acceptance Criteria
   Execute the following commands in sequence to formally validate Milestone 0:
   Step	Command	Expected Output / Acceptance Gate
4. Python Linting	ruff check backend	All checks passed! (0 errors)
5. Python Formatting	ruff format --check backend	0 files would be reformatted
6. Type Checking	mypy backend/app	Success: no issues found in X source files
7. Backend Sanity Tests	pytest backend/tests	Passed in 0.XXs (asserts /health HTTP 200 & 5 path normalization cases)
8. Frontend Linting	cd frontend && npm run lint	0 errors, 0 warnings
9. Frontend Build	cd frontend && npm run build	✓ built in XXXms (Clean dist folder)
10. Health Endpoint	curl http://localhost:8000/health	{"status":"ok","version":"0.1.0"}
3.1 Actual Verification Results (2026-11-23)
   Runtime: Python 3.11.9 (venv at backend/.venv) | Node.js v24.18.0 | npm 11.16.0
   Step	Command	Observed Output	Status
1. Python Linting	ruff check backend	All checks passed!	PASS
2. Python Formatting	ruff format --check backend	19 files already formatted	PASS
3. Type Checking	mypy backend/app	Success: no issues found in 14 source files	PASS
4. Backend Sanity Tests	pytest backend/tests	16 passed (also verified from repository root)	PASS
5. Frontend Linting	cd frontend && npm run lint	0 errors, 0 warnings	PASS
6. Frontend Build	cd frontend && npm run build	built in 12.64s (dist produced)	PASS
7. Health Endpoint	GET http://127.0.0.1:8000/health	HTTP 200 {"status":"ok","version":"0.1.0"}	PASS
   Note: The backend test suite (16 tests) covers the health endpoint and all 5 path-normalization configurations required in Phase 0.4.
4. Authorization & Sign-Off Gate
    [!IMPORTANT]
    The user explicitly authorized beginning Milestone 0 on 2026-11-23. All 7 verification commands above executed with zero errors and their actual outputs have been recorded in section 3.1. Milestone 0 is COMPLETE and verified. Development may proceed to Milestone 1 (PDF Ingestion Engine & PyMuPDF) only after explicit user approval of this completed milestone.