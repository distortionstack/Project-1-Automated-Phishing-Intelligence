from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import pandas as pd

from .browser import BrowserInstrument
from .config import DEFAULT_SETTINGS, Settings
from .contracts import PageSnapshot, PipelineArtifacts, UrlRecord
from .features import VisualFeatureExtractor, extract_html_features, extract_url_features
from .ingestion import DataIngestion
from .model import PhishingClassifier
from .reporting import PhishingReporter

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str, int], None]


def run_pipeline(
    n_urls: int = 20,
    use_browser: bool = True,
    offline_only: bool = False,
    settings: Settings | None = None,
) -> PipelineArtifacts:
    settings = settings or DEFAULT_SETTINGS
    settings.ensure_output_dirs()

    ingester = DataIngestion(settings)
    records = ingester.get_url_records(
        n_phish=n_urls // 2,
        n_benign=n_urls // 2,
        offline_only=offline_only,
    )
    return run_labeled_dataset(
        records=records,
        settings=settings,
        use_browser=use_browser,
        offline_only=offline_only,
    )


def run_analysis(
    urls: list[str],
    use_browser: bool = True,
    offline_only: bool = False,
    settings: Settings | None = None,
    job_id: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> PipelineArtifacts:
    settings = settings or DEFAULT_SETTINGS
    job_settings = _job_settings(settings, job_id)
    job_settings.ensure_output_dirs()

    reference_features, reference_labels = load_or_build_reference_dataset(
        settings=settings,
        use_browser=use_browser,
        offline_only=offline_only,
        progress_callback=progress_callback,
    )

    classifier = PhishingClassifier(job_settings)
    _notify(progress_callback, "model", "training reference model", 65)
    metrics = classifier.train(reference_features, reference_labels)

    _notify(progress_callback, "capture", "capturing submitted URLs", 75)
    user_records = [UrlRecord(url=url, label=0, source="user_input") for url in urls]
    user_snapshots = capture_records(
        records=user_records,
        settings=job_settings,
        use_browser=use_browser,
        offline_only=offline_only,
    )

    _notify(progress_callback, "extract", "extracting submitted URL features", 85)
    user_features = build_feature_frame(user_snapshots, job_settings)
    probabilities, predictions = classifier.predict(user_features)
    explanations = classifier.explain(user_features, probabilities, predictions)

    reporter = PhishingReporter()
    _notify(progress_callback, "report", "building report artifacts", 95)
    prediction_rows = reporter.build_predictions(
        urls=urls,
        labels=[None for _ in urls],
        snapshots=user_snapshots,
        model_artifacts=explanations,
    )
    report_df = reporter.to_dataframe(prediction_rows)

    feature_output = user_features.copy()
    feature_output["url"] = urls
    feature_output.to_csv(job_settings.features_path, index=False)
    reporter.save_report(report_df, job_settings.report_path)
    reporter.save_metrics(metrics, explanations.global_importance, job_settings.metrics_path)
    _notify(progress_callback, "completed", "analysis completed", 100)

    return PipelineArtifacts(
        features=feature_output,
        report=report_df,
        metrics=metrics,
        features_path=job_settings.features_path,
        report_path=job_settings.report_path,
        metrics_path=job_settings.metrics_path,
        output_dir=job_settings.output_dir,
        screenshots=[snapshot.screenshot_path or "" for snapshot in user_snapshots],
        global_importance=explanations.global_importance,
    )


def run_labeled_dataset(
    records: list[UrlRecord],
    settings: Settings,
    use_browser: bool,
    offline_only: bool,
) -> PipelineArtifacts:
    settings.ensure_output_dirs()

    snapshots = capture_records(
        records=records,
        settings=settings,
        use_browser=use_browser,
        offline_only=offline_only,
    )

    features = build_feature_frame(snapshots, settings)
    labels = pd.Series([record.label for record in records])
    urls = [record.url for record in records]

    classifier = PhishingClassifier(settings)
    metrics = classifier.train(features, labels)
    probabilities, predictions = classifier.predict(features)
    explanations = classifier.explain(features, probabilities, predictions)

    reporter = PhishingReporter()
    prediction_rows = reporter.build_predictions(urls, labels.tolist(), snapshots, explanations)
    report_df = reporter.to_dataframe(prediction_rows)

    feature_output = features.copy()
    feature_output["url"] = urls
    feature_output["label"] = labels.values
    feature_output.to_csv(settings.features_path, index=False)
    reporter.save_report(report_df, settings.report_path)
    reporter.save_metrics(metrics, explanations.global_importance, settings.metrics_path)

    logger.info("Artifacts saved to %s", settings.output_dir)
    return PipelineArtifacts(
        features=feature_output,
        report=report_df,
        metrics=metrics,
        features_path=settings.features_path,
        report_path=settings.report_path,
        metrics_path=settings.metrics_path,
        output_dir=settings.output_dir,
        screenshots=[snapshot.screenshot_path or "" for snapshot in snapshots],
        global_importance=explanations.global_importance,
    )


def load_or_build_reference_dataset(
    settings: Settings,
    use_browser: bool,
    offline_only: bool,
    progress_callback: ProgressCallback | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
    cache_path = settings.output_dir / "reference_features.csv"
    if cache_path.exists():
        cached = pd.read_csv(cache_path)
        if "label" in cached.columns:
            _notify(progress_callback, "ingest", "loaded cached reference dataset", 20)
            labels = cached["label"].astype(int)
            features = cached.drop(columns=["label", "url"], errors="ignore").fillna(0)
            validate_feature_frame(features)
            return features, labels

    _notify(progress_callback, "ingest", "building reference dataset", 10)
    ingester = DataIngestion(settings)
    reference_records = ingester.get_url_records(n_phish=10, n_benign=10, offline_only=offline_only)

    _notify(progress_callback, "capture", "capturing reference dataset", 30)
    reference_snapshots = capture_records(
        records=reference_records,
        settings=settings,
        use_browser=use_browser,
        offline_only=offline_only,
    )

    _notify(progress_callback, "extract", "extracting reference features", 50)
    reference_features = build_feature_frame(reference_snapshots, settings)
    labels = pd.Series([record.label for record in reference_records], name="label")

    cached_output = reference_features.copy()
    cached_output["url"] = [record.url for record in reference_records]
    cached_output["label"] = labels.values
    cached_output.to_csv(cache_path, index=False)
    return reference_features, labels


def capture_records(
    records: list[UrlRecord],
    settings: Settings,
    use_browser: bool,
    offline_only: bool,
) -> list[PageSnapshot]:
    browser = BrowserInstrument(
        settings=settings,
        use_browser=use_browser,
        allow_network_fallback=not offline_only,
    )
    return [browser.capture(record, idx) for idx, record in enumerate(records)]


def build_feature_frame(snapshots: list[PageSnapshot], settings: Settings) -> pd.DataFrame:
    visual_extractor = VisualFeatureExtractor(settings)
    rows = []
    for snapshot in snapshots:
        row = {}
        row.update(extract_url_features(snapshot.url, settings))
        row.update(extract_html_features(snapshot.html))
        row.update(visual_extractor.extract(snapshot.screenshot_path, snapshot.url))
        row["load_time_ms"] = snapshot.load_time_ms
        row["status_code"] = snapshot.status_code
        row["fallback_used"] = int(snapshot.fallback_used)
        row["capture_mode_browser"] = int(snapshot.capture_mode == "browser")
        rows.append(row)

    feature_frame = pd.DataFrame(rows).fillna(0)
    validate_feature_frame(feature_frame)
    return feature_frame


def validate_feature_frame(feature_frame: pd.DataFrame) -> None:
    required_columns = {
        "url_length",
        "n_password_inputs",
        "status_code",
        "fallback_used",
    }
    missing = required_columns.difference(feature_frame.columns)
    if missing:
        raise ValueError(f"Feature matrix missing required columns: {sorted(missing)}")
    if feature_frame.empty:
        raise ValueError("Feature matrix must not be empty")


def _job_settings(settings: Settings, job_id: str | None) -> Settings:
    if not job_id:
        return settings
    return settings.with_output_dir(settings.jobs_dir / job_id)


def _notify(callback: ProgressCallback | None, stage: str, message: str, progress: int) -> None:
    if callback is not None:
        callback(stage, message, progress)
