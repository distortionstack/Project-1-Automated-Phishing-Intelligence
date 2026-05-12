from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes.api import router as api_router
from app.routes.pages import router as pages_router
from src.phishing_intel import DEFAULT_SETTINGS

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Phishing Intelligence Dashboard", version="0.1.0")
DEFAULT_SETTINGS.ensure_output_dirs()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/job-artifacts", StaticFiles(directory=str(DEFAULT_SETTINGS.jobs_dir)), name="job-artifacts")

app.include_router(pages_router)
app.include_router(api_router)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
