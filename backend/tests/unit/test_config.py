"""Working-directory-independent path resolution tests for ``app.config``.

Covers the five required normalization scenarios:
1. Default configuration.
2. Relative ``DATABASE_URL`` override.
3. Relative ``PAPERMIND_DATA_DIR`` override with ``DATABASE_URL`` unset.
4. Explicit absolute database paths.
5. Identical resolution when executed from the repository root and the backend
   directory.
"""

from pathlib import Path

import pytest

from app.config import REPO_ROOT, Settings

DATA_ENV_VARS = ("PAPERMIND_DATA_DIR", "DATABASE_URL")


def _database_file_path(database_url: str) -> Path:
    """Return the filesystem path encoded in a normalized SQLite URL."""
    assert database_url.startswith("sqlite:///")
    return Path(database_url[len("sqlite:///") :])


def _load_settings() -> Settings:
    """Instantiate settings while ignoring any developer ``.env`` file."""
    return Settings(_env_file=None)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ignore inherited storage overrides for every test in this module."""
    for variable in DATA_ENV_VARS:
        monkeypatch.delenv(variable, raising=False)


def test_default_configuration_uses_repository_data_directory() -> None:
    """Scenario 1: defaults anchor to <repo_root>/data and data/metadata.db."""
    loaded = _load_settings()
    expected_database = (REPO_ROOT / "data" / "metadata.db").resolve()

    assert loaded.resolved_data_dir == (REPO_ROOT / "data").resolve()
    assert _database_file_path(loaded.resolved_database_url) == expected_database


def test_relative_database_url_resolves_against_repository_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario 2: a relative DATABASE_URL resolves against REPO_ROOT."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./custom_db/test.db")

    loaded = _load_settings()
    expected_database = (REPO_ROOT / "custom_db" / "test.db").resolve()

    assert _database_file_path(loaded.resolved_database_url) == expected_database
    assert loaded.resolved_data_dir == (REPO_ROOT / "data").resolve()


def test_relative_data_dir_override_reanchors_default_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario 3: a relative data dir re-anchors the default database path."""
    monkeypatch.setenv("PAPERMIND_DATA_DIR", "./custom_data")

    loaded = _load_settings()
    expected_database = (REPO_ROOT / "custom_data" / "metadata.db").resolve()

    assert loaded.resolved_data_dir == (REPO_ROOT / "custom_data").resolve()
    assert _database_file_path(loaded.resolved_database_url) == expected_database


def test_absolute_database_url_is_preserved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario 4a: an absolute SQLite URL keeps its absolute location."""
    absolute_database = (tmp_path / "library" / "absolute.db").resolve()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{absolute_database.as_posix()}")

    loaded = _load_settings()

    assert _database_file_path(loaded.resolved_database_url) == absolute_database


def test_posix_style_absolute_database_url_round_trips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario 4b: four-slash absolute SQLite URLs survive normalization."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:////var/lib/papermind/metadata.db")

    loaded = _load_settings()

    assert loaded.resolved_database_url == "sqlite:////var/lib/papermind/metadata.db"


def test_absolute_data_dir_override_is_preserved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario 4c: an absolute PAPERMIND_DATA_DIR is preserved and used."""
    absolute_data_dir = (tmp_path / "store").resolve()
    monkeypatch.setenv("PAPERMIND_DATA_DIR", absolute_data_dir.as_posix())

    loaded = _load_settings()

    assert loaded.resolved_data_dir == absolute_data_dir
    expected_database = absolute_data_dir / "metadata.db"
    assert _database_file_path(loaded.resolved_database_url) == expected_database


def test_resolution_is_identical_across_working_directories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario 5: defaults resolve identically from any working directory."""
    expected_database = (REPO_ROOT / "data" / "metadata.db").resolve()
    resolved: set[Path] = set()

    for working_directory in (REPO_ROOT, REPO_ROOT / "backend", tmp_path):
        monkeypatch.chdir(working_directory)
        loaded = _load_settings()
        resolved.add(_database_file_path(loaded.resolved_database_url))

    assert resolved == {expected_database}


def test_relative_overrides_are_identical_across_working_directories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario 5b: relative overrides resolve identically from any working dir."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./custom_db/test.db")
    resolved: set[str] = set()

    for working_directory in (REPO_ROOT, REPO_ROOT / "backend"):
        monkeypatch.chdir(working_directory)
        resolved.add(_load_settings().resolved_database_url)

    assert len(resolved) == 1


def test_settings_do_not_create_database_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Configuration resolution alone must not touch the filesystem."""
    database = tmp_path / "nested" / "metadata.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database.as_posix()}")

    loaded = _load_settings()

    assert loaded.database_path == database
    assert not database.exists()


def test_ensure_directories_creates_storage_layout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Storage directories are created on demand, not on import."""
    data_dir = (tmp_path / "store").resolve()
    monkeypatch.setenv("PAPERMIND_DATA_DIR", data_dir.as_posix())

    loaded = _load_settings()
    loaded.ensure_directories()

    assert (data_dir / "raw_papers").is_dir()
    assert (data_dir / "vector_indices").is_dir()
    assert (data_dir / "metadata.db").parent.is_dir()
    assert not (data_dir / "metadata.db").exists()
