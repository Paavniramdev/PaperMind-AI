"""Architectural boundary checks for ``app/core``.

M1_ARCHITECTURE.md section 1.4 is non-negotiable: the domain layer must stay
framework-free, and PyMuPDF types must not leak into the public domain models.
These tests fail loudly if a future change breaks that boundary.
"""

from __future__ import annotations

import ast
from pathlib import Path

import app.core

FORBIDDEN_IMPORT_ROOTS = frozenset({"fastapi", "starlette", "sqlalchemy"})
MODEL_MODULES = ("ingestion/models.py", "chunking/models.py")


def core_root() -> Path:
    """Filesystem path of the ``app/core`` package."""
    assert app.core.__file__ is not None
    return Path(app.core.__file__).parent


def core_python_files() -> list[Path]:
    """Every Python module inside ``app/core``, in a deterministic order."""
    return sorted(core_root().rglob("*.py"))


def imported_roots(path: Path) -> set[str]:
    """Top-level module names imported by a file (absolute imports only)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_core_package_contains_modules() -> None:
    """Guard: an empty scan would make the boundary checks vacuous."""
    assert core_python_files()


def test_core_imports_no_web_framework_or_orm() -> None:
    """No module under app/core imports FastAPI, Starlette or SQLAlchemy."""
    offenders = {
        str(path.relative_to(core_root())): sorted(imported_roots(path) & FORBIDDEN_IMPORT_ROOTS)
        for path in core_python_files()
    }

    assert {path: found for path, found in offenders.items() if found} == {}


def test_domain_models_do_not_import_pymupdf() -> None:
    """PyMuPDF must not leak into the public domain models."""
    offenders = {
        relative
        for relative in MODEL_MODULES
        if "pymupdf" in imported_roots(core_root() / relative)
    }

    assert offenders == set()
