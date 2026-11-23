"""Authoritative runtime configuration for the PaperMind AI backend.

Path resolution is anchored to the repository root derived from this module's
own location, so tests, CLI commands, and the Uvicorn server always resolve the
same data directory and SQLite database regardless of the current working
directory.

Importing this module never creates files or directories; the storage layout is
materialized on demand through :meth:`Settings.ensure_directories`.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.ingestion.config import (
    BYTES_PER_MEGABYTE,
    DEFAULT_INGESTION_LIMITS,
    DEFAULT_MAX_PDF_SIZE_MB,
    IngestionLimits,
)

# <repo_root>/backend/app/config.py -> parent.parent.parent == <repo_root>
REPO_ROOT: Path = Path(__file__).resolve().parent.parent.parent

ENV_FILE: Path = REPO_ROOT / ".env"

DATA_DIR_NAME: str = "data"
DATABASE_FILENAME: str = "metadata.db"
SQLITE_PREFIX: str = "sqlite:///"


def _sqlite_url(path: Path) -> str:
    """Build a normalized absolute SQLite URL for a filesystem path."""
    posix_path = path.as_posix()
    if posix_path.startswith("/"):
        return f"{SQLITE_PREFIX}/{posix_path.lstrip('/')}"
    return f"{SQLITE_PREFIX}{posix_path}"


class Settings(BaseSettings):
    """Runtime settings with working-directory-independent path resolution."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PAPERMIND_ENV: str = "development"
    PAPERMIND_DATA_DIR: Path = Path(DATA_DIR_NAME)
    DATABASE_URL: str | None = None
    EMBEDDING_MODEL_ID: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DEVICE: str = "cpu"
    RETRIEVAL_ABSTENTION_THRESHOLD: float = 0.40
    MAX_PDF_SIZE_MB: int = DEFAULT_MAX_PDF_SIZE_MB
    MIN_PDF_PAGE_COUNT: int = DEFAULT_INGESTION_LIMITS.min_page_count
    SCANNED_PAGE_CHAR_THRESHOLD: int = DEFAULT_INGESTION_LIMITS.scanned_page_char_threshold
    SCANNED_PAGE_RATIO: float = DEFAULT_INGESTION_LIMITS.scanned_page_ratio
    SCANNED_DENSITY_THRESHOLD: float = DEFAULT_INGESTION_LIMITS.scanned_density_threshold
    LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    CORS_ORIGINS: str = "http://localhost:5173"

    def _anchor(self, raw_path: str | Path) -> Path:
        """Resolve a possibly relative path against the repository root."""
        path = Path(raw_path).expanduser()
        if path.is_absolute():
            return path
        return (REPO_ROOT / path).resolve()

    @property
    def resolved_data_dir(self) -> Path:
        """Absolute data directory; relative overrides anchor to REPO_ROOT."""
        return self._anchor(self.PAPERMIND_DATA_DIR)

    @property
    def resolved_database_url(self) -> str:
        """Absolute SQLite URL; relative overrides anchor to REPO_ROOT."""
        raw_url = (self.DATABASE_URL or "").strip()
        if not raw_url:
            return _sqlite_url(self.resolved_data_dir / DATABASE_FILENAME)
        if raw_url.startswith(f"{SQLITE_PREFIX}/"):
            # Four-slash form is absolute by definition: "sqlite:////abs/path".
            remainder = raw_url[len(SQLITE_PREFIX) :]
            if remainder.startswith("/") and remainder[2:3] == ":":
                # Windows drive form: "sqlite:////C:/data/x.db".
                remainder = remainder[1:]
            return _sqlite_url(Path(remainder))
        if raw_url.startswith(SQLITE_PREFIX):
            return _sqlite_url(self._anchor(raw_url[len(SQLITE_PREFIX) :]))
        if "://" not in raw_url:
            # A bare filesystem path, e.g. "./data/metadata.db" or "C:/data/x.db".
            return _sqlite_url(self._anchor(raw_url))
        return raw_url

    @property
    def database_path(self) -> Path | None:
        """Filesystem path of the SQLite database, or None for other dialects."""
        url = self.resolved_database_url
        if not url.startswith(SQLITE_PREFIX):
            return None
        return Path(url[len(SQLITE_PREFIX) :])

    @property
    def ingestion_limits(self) -> IngestionLimits:
        """Immutable ingestion limits built from the environment-overridable settings.

        ``app/core`` stays framework-free: this module adapts the settings into the
        plain value object the validator consumes through dependency injection.
        """
        return IngestionLimits(
            max_pdf_size_bytes=self.MAX_PDF_SIZE_MB * BYTES_PER_MEGABYTE,
            min_page_count=self.MIN_PDF_PAGE_COUNT,
            scanned_page_char_threshold=self.SCANNED_PAGE_CHAR_THRESHOLD,
            scanned_page_ratio=self.SCANNED_PAGE_RATIO,
            scanned_density_threshold=self.SCANNED_DENSITY_THRESHOLD,
        )

    def ensure_directories(self) -> None:
        """Create the local storage layout on demand (never during import)."""
        data_dir = self.resolved_data_dir
        (data_dir / "raw_papers").mkdir(parents=True, exist_ok=True)
        (data_dir / "vector_indices").mkdir(parents=True, exist_ok=True)
        database_path = self.database_path
        if database_path is not None:
            database_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
