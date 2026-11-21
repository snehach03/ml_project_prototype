"""
Model inference used by the live backend.

Nothing in here is hard-coded or simulated: the saved models are loaded from
models/*.joblib and every score is a real model output.

Important honesty rules built into the output:
  * the score is a model score in 0..1, NOT a calibrated probability
  * it is only meaningful RELATIVE to the user's own baseline
  * 'leaning' is 'unclear' inside the 0.40-0.60 band
  * the workload model is returned with reliable=False whenever its own
    leave-one-subject-out evaluation did not show a reliable signal
"""

import os

import joblib
import numpy as np
import pandas as pd

from ml import config, features
from ml.explain import ShapExplainer, plain_name
from ml.transformers import Winsorizer  # noqa: F401  (needed to unpickle)

UNCLEAR_LOW = 0.40
UNCLEAR_HIGH = 0.60
SMOOTHING_WINDOWS = 3
TOP_CONTRIBUTIONS = 5


class ModelService:
    def __init__(self, models_dir=None):
        if models_dir is None:
            models_dir = config.MODELS_DIR
        self.models_dir = models_dir
        self.bundles = {}
        self.explainers = {}
        self._load("stress", "stress_model.joblib")
        self._load("workload", "workload_model.joblib")

    def _load(self, key, file_name):
        path = os.path.join(self.models_dir, file_name)
        if not os.path.exists(path):
            return
        bundle = joblib.load(path)
        self.bundles[key] = bundle
        self.explainers[key] = ShapExplainer(bundle)

    @property
    def is_ready(self):
        return "stress" in self.bundles

    def model_info(self):
        info = {}
        for key, bundle in self.bundles.items():
            info[key] = {
                "model": bundle["model_name"],
                "target": bundle["target"],
                "version": bundle["version"],
                "trained_at": bundle["trained_at"],
                "window_minutes": bundle["window_minutes"],
                "reliable_signal": bundle["reliable_signal"],
                "evidence": bundle["evidence_text"],
                "loso_block_roc_auc": bundle["loso_block_metrics"]["roc_auc"],
                "loso_block_roc_auc_ci95": bundle["loso_uncertainty"]["roc_auc"],
                "loso_block_f1": bundle["loso_block_metrics"]["f1"],
                "permutation_p": bundle["permutation_p"],
            }
        return info

    # ------------------------------------------------------------------
    # baseline
    # ------------------------------------------------------------------
    def baseline_from_sequences(self, sequences):
        """
        sequences: list of DataFrames, one per past session (columns = MINUTE_FIELDS).
        Windows never straddle two sessions. Returns a baseline dict or None.
        """
        window_rows = []
        for minutes in sequences:
            if len(minutes) >= config.WINDOW_MINUTES:
                window_rows.extend(features.make_windows_for_sequence(minutes))
        if len(window_rows) < config.MIN_BASELINE_WINDOWS:
            return None
        window_df = pd.DataFrame(window_rows)
        return features.compute_baseline(window_df)

    # ------------------------------------------------------------------
    # estimation
    # ------------------------------------------------------------------
    def estimate(self, session_minutes, history_baseline=None):
        """
        session_minutes : DataFrame, one row per minute of the CURRENT session.
        history_baseline: baseline dict built from earlier sessions, or None.
        """
        result = {"status": "ok", "baseline_source": None, "minutes_observed": int(len(session_minutes))}

        if len(session_minutes) < config.WINDOW_MINUTES:
            result["status"] = "insufficient_data"
            result["message"] = ("Need at least " + str(config.WINDOW_MINUTES)
                                 + " minutes of activity before an estimate can be made.")
            return result

        window_rows = features.make_windows_for_sequence(session_minutes)
        if len(window_rows) == 0:
            result["status"] = "insufficient_data"
            result["message"] = "No complete windows yet."
            return result

        if history_baseline is not None:
            baseline = history_baseline
            result["baseline_source"] = "previous_sessions"
        elif len(window_rows) >= config.MIN_BASELINE_WINDOWS:
            baseline = features.compute_baseline(pd.DataFrame(window_rows))
            result["baseline_source"] = "this_session_provisional"
        else:
            result["status"] = "calibrating"
            result["message"] = ("Building your personal baseline: "
                                 + str(len(window_rows)) + "/" + str(config.MIN_BASELINE_WINDOWS)
                                 + " windows collected. Estimates are relative to YOUR usual behaviour, "
                                 "so a baseline is required.")
            result["baseline_progress"] = [len(window_rows), config.MIN_BASELINE_WINDOWS]
            return result

        relative_rows = []
        for row in window_rows:
            relative_rows.append(features.to_relative(row, baseline))
        relative_df = pd.DataFrame(relative_rows)[config.MODEL_FEATURES]
        matrix = relative_df.values

        result["stress"] = self._estimate_one("stress", matrix, window_rows)
        if "workload" in self.bundles:
            result["workload"] = self._estimate_one("workload", matrix, window_rows)
        result["disclaimer"] = ("Experimental research estimate of how your current behaviour compares with "
                                "your own usual behaviour. Not a medical or psychological diagnosis.")
        return result

    def _estimate_one(self, key, matrix, window_rows):
        bundle = self.bundles[key]
        scores = bundle["pipeline"].predict_proba(matrix)[:, 1]

        recent = scores[-SMOOTHING_WINDOWS:]
        current_score = float(np.mean(recent))
        session_score = float(np.mean(scores))

        if current_score >= UNCLEAR_HIGH:
            leaning = "higher_than_usual"
        elif current_score <= UNCLEAR_LOW:
            leaning = "lower_than_usual"
        else:
            leaning = "unclear"

        margin = abs(current_score - 0.5)
        if not bundle["reliable_signal"]:
            confidence = "very_low"
        elif margin < 0.10:
            confidence = "low"
        elif margin < 0.20:
            confidence = "moderate"
        else:
            confidence = "moderate_high"

        shap_array = self.explainers[key].explain(matrix[-1:])
        contributions = self._top_contributions(shap_array[0], matrix[-1])

        timeline = []
        index = 0
        while index < len(scores):
            timeline.append({"window_end_minute": int(window_rows[index]["end_position"]) + 1,
                             "score": float(scores[index])})
            index = index + 1

        return {
            "target": bundle["target"],
            "model": bundle["model_name"],
            "score": current_score,
            "session_score": session_score,
            "leaning": leaning,
            "confidence": confidence,
            "reliable": bool(bundle["reliable_signal"]),
            "evidence": bundle["evidence_text"],
            "loso_block_roc_auc": bundle["loso_block_metrics"]["roc_auc"],
            "loso_block_roc_auc_ci95": bundle["loso_uncertainty"]["roc_auc"],
            "score_note": ("Model score, not a calibrated probability. Meaningful only relative to "
                           "your own baseline."),
            "contributions": contributions,
            "timeline": timeline,
        }

    def _top_contributions(self, shap_row, relative_row):
        order = np.argsort(-np.abs(shap_row))[:TOP_CONTRIBUTIONS]
        items = []
        for position in order:
            name = config.MODEL_FEATURES[position]
            z_value = float(relative_row[position])
            shap_value = float(shap_row[position])
            if z_value >= 0:
                level_text = format(abs(z_value), ".1f") + " SD above your usual"
            else:
                level_text = format(abs(z_value), ".1f") + " SD below your usual"
            if shap_value >= 0:
                effect = "pushed the estimate toward 'higher than usual'"
            else:
                effect = "pushed the estimate toward 'lower than usual'"
            items.append({
                "feature": name,
                "description": plain_name(name),
                "relative_value_sd": z_value,
                "shap": shap_value,
                "direction": "up" if shap_value >= 0 else "down",
                "explanation": plain_name(name).capitalize() + " was " + level_text + "; this " + effect + ".",
            })
        return items
