from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import AnalyzeRequest, AnalyzeResponse, JobResultsResponse, JobSummary
from app.services.analysis_service import analysis_service

router = APIRouter(prefix="/api", tags=["api"])


@router.post("/analyze", response_model=AnalyzeResponse)
def create_analysis_job(payload: AnalyzeRequest) -> AnalyzeResponse:
    cleaned_urls = [url.strip() for url in payload.urls if url.strip()]
    if not cleaned_urls:
        raise HTTPException(status_code=400, detail="At least one URL is required")

    job = analysis_service.create_job(
        urls=cleaned_urls,
        use_browser=payload.use_browser,
        offline_only=payload.offline_only,
    )
    return AnalyzeResponse(job_id=job.job_id, status=job.status, detail=job.message)


@router.get("/jobs/{job_id}", response_model=JobSummary)
def get_job(job_id: str) -> JobSummary:
    job = analysis_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobSummary(**analysis_service.serialize_job(job))


@router.get("/jobs/{job_id}/results", response_model=JobResultsResponse)
def get_job_results(job_id: str) -> JobResultsResponse:
    job = analysis_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=409, detail="Job has not completed yet")
    return JobResultsResponse(**analysis_service.get_job_results(job_id))


@router.get("/jobs/{job_id}/artifacts")
def get_job_artifacts(job_id: str) -> dict:
    job = analysis_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return analysis_service.get_artifacts(job_id)


@router.get("/history", response_model=list[JobSummary])
def get_history() -> list[JobSummary]:
    return [JobSummary(**analysis_service.serialize_job(job)) for job in analysis_service.list_jobs()]
