from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    urls: list[str] = Field(min_length=1)
    use_browser: bool = True
    offline_only: bool = False


class AnalyzeResponse(BaseModel):
    job_id: str
    status: str
    detail: str


class ArtifactLinks(BaseModel):
    report_csv: str
    features_csv: str
    metrics_json: str
    screenshots: list[str]


class JobSummary(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: int
    stage: str
    message: str
    created_at: str
    updated_at: str
    urls: list[str]
    use_browser: bool
    offline_only: bool
    error: str | None = None
    artifacts: ArtifactLinks | None = None


class JobResultsResponse(BaseModel):
    job: JobSummary
    metrics: dict[str, Any]
    report_rows: list[dict[str, Any]]
    global_importance: list[tuple[str, float]]
