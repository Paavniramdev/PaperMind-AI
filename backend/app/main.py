"""FastAPI application entrypoint for the PaperMind AI Milestone 0 scaffold."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import __version__
from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create the local storage layout before the server accepts requests."""
    settings.ensure_directories()
    yield


app = FastAPI(
    title="PaperMind AI",
    description="Research Intelligence Platform - backend API (Milestone 0 scaffold).",
    version=__version__,
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe consumed by the frontend status screen."""
    return {"status": "ok", "version": __version__}
