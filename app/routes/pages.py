from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services.analysis_service import analysis_service

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    history = [analysis_service.serialize_job(job) for job in analysis_service.list_jobs()[:10]]
    return templates.TemplateResponse(name="index.html", request=request, context={"history": history})


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def processing(request: Request, job_id: str) -> HTMLResponse:
    job = analysis_service.get_job(job_id)
    if job is None:
        return templates.TemplateResponse(name="404.html", request=request, context={}, status_code=404)
    if job.status == "completed":
        return RedirectResponse(url=f"/jobs/{job_id}/result", status_code=302)
    return templates.TemplateResponse(
        name="processing.html",
        request=request,
        context={"job": analysis_service.serialize_job(job)},
    )


@router.get("/jobs/{job_id}/result", response_class=HTMLResponse)
def result_dashboard(request: Request, job_id: str) -> HTMLResponse:
    job = analysis_service.get_job(job_id)
    if job is None:
        return templates.TemplateResponse(name="404.html", request=request, context={}, status_code=404)
    if job.status != "completed":
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=302)

    data = analysis_service.get_job_results(job_id)
    history = [analysis_service.serialize_job(item) for item in analysis_service.list_jobs()[:10]]
    return templates.TemplateResponse(
        name="result.html",
        request=request,
        context={
            "job": data["job"],
            "metrics": data["metrics"],
            "report_rows": data["report_rows"],
            "global_importance": data["global_importance"],
            "history": history,
        },
    )


@router.get("/history", response_class=HTMLResponse)
def history(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        name="history.html",
        request=request,
        context={"jobs": [analysis_service.serialize_job(job) for job in analysis_service.list_jobs()]},
    )
