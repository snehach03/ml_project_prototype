"""
Phase 4 - SHAP explainability.

ShapExplainer picks the right SHAP algorithm for whichever model won
(tree models -> TreeExplainer, logistic regression -> LinearExplainer,
SVM / anything else -> KernelExplainer with a small k-means background).

SHAP values are always for the POSITIVE class ("higher than usual").

    python -m ml.explain        # writes global SHAP figure + models/shap_global.json
"""

import json
import os

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import shap
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

from ml import config
from ml.transformers import Winsorizer  # noqa: F401  (needed so joblib can unpickle bundles)


class ShapExplainer:
    def __init__(self, bundle):
        self.bundle = bundle
        self.feature_names = bundle["feature_names"]
        self.pipeline = bundle["pipeline"]
        self.preprocessor = self.pipeline[:-1]
        self.classifier = self.pipeline[-1]

        background_raw = bundle["background_X"]
        background = self.preprocessor.transform(background_raw)

        if isinstance(self.classifier, (RandomForestClassifier, XGBClassifier)):
            self.kind = "tree"
            self.explainer = shap.TreeExplainer(self.classifier, data=background,
                                                feature_perturbation="interventional")
        elif isinstance(self.classifier, LogisticRegression):
            self.kind = "linear"
            self.explainer = shap.LinearExplainer(self.classifier, background)
        else:
            self.kind = "kernel"
            summary = shap.kmeans(background, 20)

            def positive_probability(values):
                return self.classifier.predict_proba(values)[:, 1]

            self.explainer = shap.KernelExplainer(positive_probability, summary)

    def explain(self, relative_features):
        """relative_features: array (n, n_features) of rel_* values -> SHAP array (n, n_features)."""
        values = np.asarray(relative_features, dtype=float)
        if values.ndim == 1:
            values = values.reshape(1, -1)
        prepared = self.preprocessor.transform(values)
        if self.kind == "kernel":
            shap_values = self.explainer.shap_values(prepared, nsamples=150, silent=True)
        else:
            shap_values = self.explainer.shap_values(prepared)
        shap_array = np.asarray(shap_values)
        # newer shap returns (n, features, classes) for sklearn forests; older returns a list
        if isinstance(shap_values, list):
            shap_array = np.asarray(shap_values[1])
        if shap_array.ndim == 3:
            shap_array = shap_array[:, :, 1]
        return shap_array


def plain_name(feature_name):
    base = feature_name.replace("rel_", "", 1)
    return config.FEATURE_DESCRIPTIONS.get(base, base)


def global_importance(shap_array, feature_names):
    mean_abs = np.abs(shap_array).mean(axis=0)
    ranking = []
    index = 0
    while index < len(feature_names):
        ranking.append({
            "feature": feature_names[index],
            "description": plain_name(feature_names[index]),
            "mean_abs_shap": float(mean_abs[index]),
        })
        index = index + 1
    ranking.sort(key=lambda item: item["mean_abs_shap"], reverse=True)
    return ranking


def main(sample_size=150):
    from ml import features, preprocessing

    bundle = joblib.load(os.path.join(config.MODELS_DIR, "stress_model.joblib"))
    explainer = ShapExplainer(bundle)
    print("model:", bundle["model_name"], "| SHAP algorithm:", explainer.kind)

    dataset = features.build_dataset(preprocessing.load_minute_data(), preprocessing.load_labels())
    sample = dataset.sample(n=min(sample_size, len(dataset)), random_state=config.RANDOM_STATE)
    values = sample[config.MODEL_FEATURES].values
    shap_array = explainer.explain(values)

    ranking = global_importance(shap_array, config.MODEL_FEATURES)
    with open(os.path.join(config.MODELS_DIR, "shap_global.json"), "w", encoding="utf-8") as handle:
        json.dump({"model": bundle["model_name"], "algorithm": explainer.kind,
                   "n_samples": int(len(sample)), "ranking": ranking}, handle, indent=2)

    os.makedirs(config.FIGURES_DIR, exist_ok=True)
    prepared = explainer.preprocessor.transform(values)
    plt.figure()
    shap.summary_plot(shap_array, prepared, feature_names=config.MODEL_FEATURES, show=False, max_display=12)
    plt.tight_layout()
    plt.savefig(os.path.join(config.FIGURES_DIR, "shap_summary_stress.png"), dpi=130, bbox_inches="tight")
    plt.close()

    print("Top features by mean |SHAP|:")
    for item in ranking[:8]:
        print("  ", format(item["mean_abs_shap"], ".4f"), item["feature"], "-", item["description"])


if __name__ == "__main__":
    main()
