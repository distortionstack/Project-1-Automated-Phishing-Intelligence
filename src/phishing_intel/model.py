from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler

try:
    import shap
except ImportError:
    shap = None

try:
    import xgboost as xgb
except ImportError:
    xgb = None

from .config import Settings
from .contracts import ModelArtifacts

logger = logging.getLogger(__name__)


class PhishingClassifier:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            class_weight="balanced",
            random_state=settings.random_seed,
            n_jobs=-1,
        )
        self.xgb = (
            xgb.XGBClassifier(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.1,
                use_label_encoder=False,
                eval_metric="logloss",
                random_state=settings.random_seed,
                verbosity=0,
            )
            if xgb is not None
            else None
        )
        self.scaler = StandardScaler()
        self.feature_names: list[str] = []
        self.best_model = None

    def train(self, X: pd.DataFrame, y: pd.Series) -> dict[str, object]:
        self._validate_labels(y)
        self.feature_names = list(X.columns)

        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=0.3,
            random_state=self.settings.random_seed,
            stratify=y,
        )

        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        cv_folds = min(5, int(y_train.value_counts().min()))
        metrics: dict[str, object] = {}
        for name, estimator in self._estimators():
            if cv_folds >= 2:
                splitter = StratifiedKFold(
                    n_splits=cv_folds,
                    shuffle=True,
                    random_state=self.settings.random_seed,
                )
                scores = cross_val_score(estimator, X_train_scaled, y_train, cv=splitter, scoring="f1", n_jobs=-1)
                metrics[f"{name}_cv_f1_mean"] = float(scores.mean())
                metrics[f"{name}_cv_f1_std"] = float(scores.std())
            else:
                metrics[f"{name}_cv_f1_mean"] = None
                metrics[f"{name}_cv_f1_std"] = None

            estimator.fit(X_train_scaled, y_train)

        self.best_model = self.rf
        probabilities = self._predict_proba_scaled(X_test_scaled)
        predictions = (probabilities >= 0.5).astype(int)

        metrics.update(
            {
                "test_f1": float(f1_score(y_test, predictions, zero_division=0)),
                "test_precision": float(precision_score(y_test, predictions, zero_division=0)),
                "test_recall": float(recall_score(y_test, predictions, zero_division=0)),
                "test_confusion_matrix": confusion_matrix(y_test, predictions).tolist(),
                "test_classification_report": classification_report(
                    y_test,
                    predictions,
                    target_names=["Benign", "Phishing"],
                    output_dict=True,
                    zero_division=0,
                ),
                "train_size": int(len(X_train)),
                "test_size": int(len(X_test)),
                "xgboost_enabled": self.xgb is not None,
            }
        )

        logger.info(
            "Model evaluation complete: F1=%.3f Precision=%.3f Recall=%.3f",
            metrics["test_f1"],
            metrics["test_precision"],
            metrics["test_recall"],
        )
        return metrics

    def predict(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        scaled = self.scaler.transform(X)
        probabilities = self._predict_proba_scaled(scaled)
        predictions = (probabilities >= 0.5).astype(int)
        return probabilities, predictions

    def explain(self, X: pd.DataFrame, probabilities: np.ndarray, predictions: np.ndarray) -> ModelArtifacts:
        local_explanations: list[list[str]] = []
        global_importance: list[tuple[str, float]] = []

        if shap is not None and self.best_model is not None:
            try:
                scaled = self.scaler.transform(X)
                explainer = shap.TreeExplainer(self.best_model)
                shap_values = explainer.shap_values(scaled)
                shap_array = np.array(shap_values)
                if shap_array.ndim == 3:
                    local_values = shap_array[:, :, 1]
                elif isinstance(shap_values, list):
                    local_values = np.array(shap_values[1])
                else:
                    local_values = shap_array

                for row_idx in range(len(X)):
                    shap_row = np.array(local_values[row_idx]).flatten()
                    top_indices = np.argsort(np.abs(shap_row))[::-1][:5]
                    reasons = []
                    for idx in top_indices:
                        feature_name = self.feature_names[int(idx)]
                        feature_value = X.iloc[row_idx][feature_name]
                        impact = "up_phish" if shap_row[idx] > 0 else "down_benign"
                        reasons.append(f"{feature_name}={float(feature_value):.2f}({impact})")
                    local_explanations.append(reasons)

                mean_abs = np.abs(np.array(local_values)).mean(axis=0).flatten()
                top_global = np.argsort(mean_abs)[::-1][:10].tolist()
                global_importance = [
                    (self.feature_names[int(index)], round(float(mean_abs[index]), 4))
                    for index in top_global
                ]
            except Exception as exc:
                logger.warning("SHAP explanation failed, using fallback reasons: %s", exc)

        if not local_explanations:
            local_explanations = self._fallback_explanations(X, probabilities)
        if not global_importance:
            importances = getattr(self.rf, "feature_importances_", np.zeros(len(self.feature_names)))
            ranked = np.argsort(importances)[::-1][:10].tolist()
            global_importance = [
                (self.feature_names[int(index)], round(float(importances[index]), 4))
                for index in ranked
            ]

        return ModelArtifacts(
            feature_names=self.feature_names,
            probabilities=probabilities.tolist(),
            predictions=predictions.tolist(),
            metrics={},
            local_explanations=local_explanations,
            global_importance=global_importance,
        )

    def _predict_proba_scaled(self, scaled: np.ndarray) -> np.ndarray:
        rf_probabilities = self.rf.predict_proba(scaled)[:, 1]
        if self.xgb is None:
            return rf_probabilities
        xgb_probabilities = self.xgb.predict_proba(scaled)[:, 1]
        return (rf_probabilities + xgb_probabilities) / 2

    def _estimators(self) -> list[tuple[str, object]]:
        estimators: list[tuple[str, object]] = [("random_forest", self.rf)]
        if self.xgb is not None:
            estimators.append(("xgboost", self.xgb))
        return estimators

    @staticmethod
    def _validate_labels(y: pd.Series) -> None:
        unique_labels = set(y.unique().tolist())
        if unique_labels != {0, 1}:
            raise ValueError(f"Expected binary labels {{0, 1}}, got {unique_labels}")

    def _fallback_explanations(self, X: pd.DataFrame, probabilities: np.ndarray) -> list[list[str]]:
        explanations: list[list[str]] = []
        for row_idx in range(len(X)):
            row = X.iloc[row_idx]
            direction = "up_phish" if probabilities[row_idx] >= 0.5 else "down_benign"
            candidates = [
                ("brand_kw_in_url", row.get("brand_kw_in_url", 0)),
                ("n_password_inputs", row.get("n_password_inputs", 0)),
                ("external_action", row.get("external_action", 0)),
                ("suspicious_tld", row.get("suspicious_tld", 0)),
                ("fallback_used", row.get("fallback_used", 0)),
            ]
            ranked = sorted(candidates, key=lambda item: float(item[1]), reverse=True)[:5]
            explanations.append([f"{name}={float(value):.2f}({direction})" for name, value in ranked])
        return explanations
