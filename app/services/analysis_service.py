from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.phishing_intel import DEFAULT_SETTINGS
from src.phishing_intel.pipeline import run_analysis

logger = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobRecord:
    job_id: str
    urls: list[str]
    use_browser: bool
    offline_only: bool
    status: str = "queued"
    progress: int = 0
    stage: str = "queued"
    message: str = "waiting to start"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    error: str | None = None
    artifacts: dict[str, Any] | None = None


class AnalysisService:
    def __init__(self, settings=DEFAULT_SETTINGS):
        self.settings = settings
        self.settings.ensure_output_dirs()
        self.lock = threading.Lock()
        self.jobs: dict[str, JobRecord] = {}
        self._load_existing_jobs()

    def create_job(self, urls: list[str], use_browser: bool, offline_only: bool) -> JobRecord:
        job_id = uuid.uuid4().hex[:12]
        job = JobRecord(
            job_id=job_id,
            urls=urls,
            use_browser=use_browser,
            offline_only=offline_only,
            message="job created",
        )
        with self.lock:
            self.jobs[job_id] = job
            self._persist_job(job)

        worker = threading.Thread(target=self._run_job, args=(job_id,), daemon=True)
        worker.start()
        return job

    def list_jobs(self) -> list[JobRecord]:
        with self.lock:
            return sorted(self.jobs.values(), key=lambda job: job.created_at, reverse=True)

    def get_job(self, job_id: str) -> JobRecord | None:
        with self.lock:
            return self.jobs.get(job_id)

    def get_job_results(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)
        if job is None:
            raise KeyError(job_id)
        job_dir = self.settings.jobs_dir / job_id
        report_rows = []
        metrics = {}
        global_importance = []
        report_path = job_dir / "phishing_report.csv"
        metrics_path = job_dir / "metrics.json"
        if report_path.exists():
            report_rows = pd.read_csv(report_path).fillna("").to_dict(orient="records")
            for row in report_rows:
                screenshot_path = str(row.get("screenshot_path", "")).strip()
                row["screenshot_url"] = self._report_screenshot_url(job_id, screenshot_path) if screenshot_path else ""
        if metrics_path.exists():
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            global_importance = metrics.pop("global_feature_importance", [])
        return {
            "job": self.serialize_job(job),
            "metrics": metrics,
            "report_rows": report_rows,
            "global_importance": global_importance,
        }

    def get_artifacts(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)
        if job is None:
            raise KeyError(job_id)
        return job.artifacts or {}

    def serialize_job(self, job: JobRecord) -> dict[str, Any]:
        payload = asdict(job)
        if job.artifacts:
            payload["artifacts"] = job.artifacts
        return payload

    def _run_job(self, job_id: str) -> None:
        job = self.get_job(job_id)
        if job is None:
            return

        self._update_job(job_id, status="running", stage="queued", progress=3, message="job started")

        def progress(stage: str, message: str, percent: int) -> None:
            self._update_job(job_id, status="running", stage=stage, progress=percent, message=message)

        try:
            artifacts = run_analysis(
                urls=job.urls,
                use_browser=job.use_browser,
                offline_only=job.offline_only,
                settings=self.settings,
                job_id=job_id,
                progress_callback=progress,
            )
            artifact_links = self._artifact_links(job_id, artifacts.screenshots)
            self._update_job(
                job_id,
                status="completed",
                stage="completed",
                progress=100,
                message="analysis completed",
                artifacts=artifact_links,
            )
        except Exception as exc:
            logger.exception("Job %s failed", job_id)
            self._update_job(
                job_id,
                status="failed",
                stage="failed",
                progress=100,
                message="analysis failed",
                error=str(exc),
            )

    def _artifact_links(self, job_id: str, screenshots: list[str]) -> dict[str, Any]:
        screenshot_links = []
        for path in screenshots:
            if not path:
                continue
            screenshot_links.append(self._artifact_url(job_id, Path(path)))
        return {
            "report_csv": f"/job-artifacts/{job_id}/phishing_report.csv",
            "features_csv": f"/job-artifacts/{job_id}/features.csv",
            "metrics_json": f"/job-artifacts/{job_id}/metrics.json",
            "screenshots": screenshot_links,
        }

    def _artifact_url(self, job_id: str, path: Path) -> str:
        return f"/job-artifacts/{job_id}/{path.relative_to(self.settings.jobs_dir / job_id).as_posix()}"

    def _report_screenshot_url(self, job_id: str, screenshot_path: str) -> str:
        path = Path(screenshot_path)
        if not path.is_absolute():
            path = self.settings.jobs_dir / job_id / path
        return self._artifact_url(job_id, path)

    def _update_job(self, job_id: str, **updates: Any) -> None:
        with self.lock:
            job = self.jobs[job_id]
            for key, value in updates.items():
                setattr(job, key, value)
            job.updated_at = utc_now()
            self._persist_job(job)

    def _persist_job(self, job: JobRecord) -> None:
        job_dir = self.settings.jobs_dir / job.job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        state_path = job_dir / "job_state.json"
        state_path.write_text(json.dumps(self.serialize_job(job), indent=2), encoding="utf-8")

    def _load_existing_jobs(self) -> None:
        for state_path in sorted(self.settings.jobs_dir.glob("*/job_state.json")):
            try:
                payload = json.loads(state_path.read_text(encoding="utf-8"))
                job = JobRecord(**payload)
                self.jobs[job.job_id] = job
            except Exception as exc:
                logger.warning("Skipping unreadable job state %s: %s", state_path, exc)


analysis_service = AnalysisService()
