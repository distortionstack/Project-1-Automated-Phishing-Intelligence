from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(slots=True)
class UrlRecord:
    url: str
    label: int
    source: str


@dataclass(slots=True)
class PageSnapshot:
    url: str
    label: int
    source: str
    screenshot_path: str | None = None
    html: str = ""
    status_code: int = 0
    load_time_ms: float = 0.0
    error_reason: str | None = None
    fallback_used: bool = False
    capture_mode: str = "browser"


@dataclass(slots=True)
class PredictionResult:
    url: str
    true_label: int | None
    predicted_label: int
    probability: float
    reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ModelArtifacts:
    feature_names: list[str]
    probabilities: list[float]
    predictions: list[int]
    metrics: dict[str, Any]
    local_explanations: list[list[str]]
    global_importance: list[tuple[str, float]]


@dataclass(slots=True)
class PipelineArtifacts:
    features: pd.DataFrame
    report: pd.DataFrame
    metrics: dict[str, Any]
    features_path: Path
    report_path: Path
    metrics_path: Path
    output_dir: Path
    screenshots: list[str] = field(default_factory=list)
    global_importance: list[tuple[str, float]] = field(default_factory=list)
