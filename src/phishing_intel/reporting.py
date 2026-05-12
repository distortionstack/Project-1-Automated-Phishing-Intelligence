from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .contracts import ModelArtifacts, PageSnapshot, PredictionResult


class PhishingReporter:
    def build_predictions(
        self,
        urls: list[str],
        labels: list[int | None],
        snapshots: list[PageSnapshot],
        model_artifacts: ModelArtifacts,
    ) -> list[PredictionResult]:
        results: list[PredictionResult] = []
        for idx, url in enumerate(urls):
            snapshot = snapshots[idx]
            results.append(
                PredictionResult(
                    url=url,
                    true_label=labels[idx],
                    predicted_label=model_artifacts.predictions[idx],
                    probability=float(model_artifacts.probabilities[idx]),
                    reasons=model_artifacts.local_explanations[idx],
                    metadata={
                        "source": snapshot.source,
                        "capture_mode": snapshot.capture_mode,
                        "fallback_used": snapshot.fallback_used,
                        "error_reason": snapshot.error_reason or "",
                        "status_code": snapshot.status_code,
                        "load_time_ms": round(float(snapshot.load_time_ms), 2),
                        "screenshot_path": snapshot.screenshot_path or "",
                    },
                )
            )
        return results

    def to_dataframe(self, predictions: list[PredictionResult]) -> pd.DataFrame:
        rows = []
        for prediction in predictions:
            rows.append(
                {
                    "url": prediction.url,
                    "true_label": (
                        "PHISHING"
                        if prediction.true_label == 1
                        else "BENIGN"
                        if prediction.true_label == 0
                        else "UNKNOWN"
                    ),
                    "predicted_label": "PHISHING" if prediction.predicted_label == 1 else "BENIGN",
                    "p_phish": round(prediction.probability, 4),
                    "reason_1": prediction.reasons[0] if len(prediction.reasons) > 0 else "",
                    "reason_2": prediction.reasons[1] if len(prediction.reasons) > 1 else "",
                    "reason_3": prediction.reasons[2] if len(prediction.reasons) > 2 else "",
                    "reason_4": prediction.reasons[3] if len(prediction.reasons) > 3 else "",
                    "reason_5": prediction.reasons[4] if len(prediction.reasons) > 4 else "",
                    **prediction.metadata,
                }
            )
        return pd.DataFrame(rows)

    def save_report(self, report_df: pd.DataFrame, report_path: Path) -> None:
        report_df.to_csv(report_path, index=False)

    def save_metrics(
        self,
        metrics: dict[str, object],
        global_importance: list[tuple[str, float]],
        metrics_path: Path,
    ) -> None:
        payload = dict(metrics)
        payload["global_feature_importance"] = global_importance
        metrics_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
