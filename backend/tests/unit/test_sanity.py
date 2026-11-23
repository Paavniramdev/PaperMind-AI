"""Baseline sanity checks for the Milestone 0 application skeleton."""

import pytest
from httpx import AsyncClient

from app import __version__
from app.config import Settings
from app.main import app


async def test_health_endpoint_returns_http_200(client: AsyncClient) -> None:
    """GET /health must respond with HTTP 200."""
    response = await client.get("/health")

    assert response.status_code == 200


async def test_health_endpoint_reports_ok_status(client: AsyncClient) -> None:
    """GET /health must report status = ok."""
    response = await client.get("/health")

    assert response.json()["status"] == "ok"


async def test_health_endpoint_reports_version_0_1_0(client: AsyncClient) -> None:
    """GET /health must report version = 0.1.0."""
    response = await client.get("/health")

    assert response.json()["version"] == "0.1.0"


async def test_health_endpoint_returns_exact_payload(client: AsyncClient) -> None:
    """GET /health payload is exactly the documented contract."""
    response = await client.get("/health")

    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_application_metadata_matches_package_version() -> None:
    """The FastAPI app advertises the package version."""
    assert app.version == __version__ == "0.1.0"


def test_settings_load_environment_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings load environment values with documented defaults."""
    monkeypatch.delenv("PAPERMIND_ENV", raising=False)
    loaded = Settings(_env_file=None)

    assert loaded.PAPERMIND_ENV == "development"
