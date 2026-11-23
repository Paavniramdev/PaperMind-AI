PaperMind AI — Greenfield Local Development Setup Guide
Version: 2.3.7
Status: Approved Greenfield Specification
Runtime Environment: Python 3.11.x | Node.js 20 LTS
Deployment Model (MVP): Single-Worker Uvicorn Process (workers = 1)
Date: November 2026  
1. System Prerequisites
   Ensure your development environment meets the following specifications before beginning setup:
   - Operating System: Windows 11, macOS 13+, or Ubuntu 22.04 LTS.
   - Python: Version 3.11.x installed and accessible via PATH.
   - Node.js: Version 20.x LTS (Iron) with npm >= 10.x.
   - Git: Installed and configured.
   - Memory: Minimum 8 GB RAM (16 GB recommended).
   - Disk Space: At least 5 GB free disk space.
2. Step-by-Step Local Environment Setup
   Step 1: Clone the Repository
   git clone <your-repository-url> Papermind_antigravity
   cd Papermind_antigravity
   Step 2: Configure Environment Variables
   Copy the root environment template:
Windows (PowerShell)
Copy-Item .env.example .env
macOS / Linux
cp .env.example .env
Environment Variables Blueprint (.env.example)
Application Environment
PAPERMIND_ENV=development
Storage Paths (Resolved dynamically if left default)
PAPERMIND_DATA_DIR=./data
DATABASE_URL=sqlite:///./data/metadata.db
Embedding Engine (Introduced in Milestone 2)
EMBEDDING_MODEL_ID=BAAI/bge-small-en-v1.5
EMBEDDING_DEVICE=cpu
Retrieval Calibration (Introduced in Milestone 4)
RETRIEVAL_ABSTENTION_THRESHOLD=0.40
LLM Provider Configuration (Introduced in Milestone 4)
LLM_PROVIDER=openai
OPENAI_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434
CORS Configuration
CORS_ORIGINS=http://localhost:5173
[!NOTE]
Authoritative Path Resolution: In backend/app/config.py, both PAPERMIND_DATA_DIR and DATABASE_URL are resolved relative to the absolute repository root (REPO_ROOT = Path(file).resolve().parent.parent.parent). Whether commands are run from backend/, the repository root, or IDE test runners, the application always connects to the identical database file at <REPO_ROOT>/data/metadata.db.

Step 3: Backend Setup (Python 3.11)
1. Create and activate a dedicated virtual environment:
   Windows (PowerShell)
   python -m venv backend/.venv
   .\backend.venv\Scripts\Activate.ps1
   macOS / Linux
   python3.11 -m venv backend/.venv
   source backend/.venv/bin/activate
2. Upgrade pip and install Milestone 0 dependencies:
   pip install --upgrade pip
   pip install -e backend/
   (Note: For Milestone 0, this installs only lightweight web, validation, database, and dev dependencies. PyTorch, Sentence Transformers, and FAISS are strictly excluded until Milestones 1 and 2.)
3. Verify backend tests and code quality:
   ruff check backend
   mypy backend/app
   pytest backend/tests
   Step 4: Frontend Setup (Node.js 20 LTS)
4. Navigate to the frontend directory:
   cd frontend
5. Install frontend dependencies:
   npm install
6. Verify frontend linting and typecheck:
   npm run lint
   npm run build
7. Running the Local Development Servers
   Starting the Backend Server (Single Uvicorn Worker)
   From the backend/ directory with the virtual environment activated:
   cd backend
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --workers 1
   Alternatively, from the repository root:
   python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload --workers 1
   - Process Model: Runs strictly as a single Uvicorn worker process (workers = 1). A process-wide exclusive threading.Lock is acquired before any database mutation and held across index rebuild and publication to protect index consistency against concurrent request threads.
   - API Documentation: Open your browser at http://localhost:8000/docs (Swagger UI) or http://localhost:8000/redoc.
   - Health Check: curl http://localhost:8000/health
     Starting the Frontend Development Server
     From the frontend/ directory in a separate terminal:
     cd frontend
     npm run dev
   - Web Interface: Open your browser at http://localhost:5173.
8. Verification Workflow (Post-Milestone 5)
   Once the MVP is fully constructed through Milestone 5:
9. Open http://localhost:5173.
10. Upload a sample two-column academic PDF (e.g., Attention Is All You Need).
11. Observe real-time parsing, chunking, and deterministic manifest publication of the global FAISS index.
12. Issue a query (e.g., "What is the dimension of the key vectors in multi-head attention?").
13. Verify that:
    - The response is generated and buffered server-side.
    - Citation IDs are verified against retrieved source chunks ($1 \le N \le k$).
    - The verified response is delivered with verified source badges (VERIFIED) or an amber warning banner (PARTIAL_WARNING).
    - Clicking a verified citation badge [^N] navigates the split-screen PDF viewer directly to the cited page and highlights the source passage on the canvas.
    - Unsupported queries (similarity $< \text{threshold}$) produce the standard abstention message: "The provided document does not contain sufficient evidence to answer this question."
Authoritative MVP Index Lifecycle
Every index-changing operation builds a complete new FAISS generation from the eligible SQLite chunk set. Append-in-place is not used in the MVP. Each generation assigns contiguous generation-specific faiss_id values from 0 to N-1; chunk_id remains the permanent identity.