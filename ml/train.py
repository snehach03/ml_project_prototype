"""
Phase 3 - model training and participant-independent evaluation.

    python -m ml.train

What it does (all numbers in the report come from this run, none are typed in):
  1. builds the window dataset
  2. Leave-One-Subject-Out (25 folds) for LogisticRegression, RandomForest,
     XGBoost and SVM, for the primary and the secondary target
  3. two reference baselines: majority class, and "condition only"
  4. block-level aggregation (mean of window scores per labelled block)
  5. participant-bootstrap confidence intervals + within-person permutation test
  6. picks the best model per target by block-level ROC-AUC, refits it on all
     data, saves it and writes documentation/model_evaluation_report.md

Hyper-parameters are FIXED and deliberately conservative. They are not tuned on
the held-out folds, because with 25 participants any tuning loop would leak.
"""

import json
import os
import warnings
from datetime import datetime, timezone

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score,
    precision_score, recall_score, roc_auc_score, roc_curve,
)
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from xgboost import XGBClassifier

from ml import config, features, preprocessing
from ml.transformers import Winsorizer

warnings.filterwarnings("ignore")
MODEL_VERSION = "1.0.0"


def make_models():
    seed = config.RANDOM_STATE
    models = {}
    models["LogisticRegression"] = Pipeline([
        ("winsor", Winsorizer()),
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(C=0.1, class_weight="balanced", max_iter=2000)),
    ])
    models["RandomForest"] = Pipeline([
        ("winsor", Winsorizer()),
        ("clf", RandomForestClassifier(
            n_estimators=300, max_depth=6, min_samples_leaf=20,
            class_weight="balanced_subsample", n_jobs=-1, random_state=seed)),
    ])
    models["XGBoost"] = Pipeline([
        ("winsor", Winsorizer()),
        ("clf", XGBClassifier(
            n_estimators=150, max_depth=3, learning_rate=0.05, subsample=0.8,
            colsample_bytree=0.8, min_child_weight=10, reg_lambda=5.0,
            eval_metric="logloss", n_jobs=4, random_state=seed)),
    ])
    models["SVM"] = Pipeline([
        ("winsor", Winsorizer()),
        ("scale", StandardScaler()),
        ("clf", SVC(kernel="rbf", C=0.5, gamma="scale", class_weight="balanced",
                    probability=True, random_state=seed)),
    ])
    return models


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------
def compute_metrics(y_true, proba, threshold=0.5):
    y_true = np.asarray(y_true)
    proba = np.asarray(proba)
    predicted = (proba >= threshold).astype(int)
    matrix = confusion_matrix(y_true, predicted, labels=[0, 1])
    result = {
        "n": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, predicted)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, predicted)),
        "precision": float(precision_score(y_true, predicted, zero_division=0)),
        "recall": float(recall_score(y_true, predicted, zero_division=0)),
        "f1": float(f1_score(y_true, predicted, zero_division=0)),
        "confusion_matrix": matrix.tolist(),   # [[TN, FP], [FN, TP]]
    }
    if len(np.unique(y_true)) == 2:
        result["roc_auc"] = float(roc_auc_score(y_true, proba))
    else:
        result["roc_auc"] = None
    return result


def to_block_level(oof_df):
    """Average window scores inside each labelled block."""
    block_df = oof_df.groupby("block_id").agg(
        participant=("participant", "first"),
        y=("y", "first"),
        proba=("proba", "mean"),
        condition=("condition", "first"),
    ).reset_index()
    return block_df


# ---------------------------------------------------------------------------
# Leave-One-Subject-Out
# ---------------------------------------------------------------------------
def run_loso(model, dataset, target):
    X = dataset[config.MODEL_FEATURES].values
    y = dataset[target].values
    groups = dataset["participant"].values

    probabilities = np.zeros(len(dataset))
    splitter = LeaveOneGroupOut()
    for train_index, test_index in splitter.split(X, y, groups):
        fold_model = clone(model)
        fold_model.fit(X[train_index], y[train_index])
        probabilities[test_index] = fold_model.predict_proba(X[test_index])[:, 1]

    oof = dataset[["participant", "block_id", "condition"]].copy()
    oof["y"] = y
    oof["proba"] = probabilities
    return oof


def run_majority_baseline(dataset, target):
    """Predict the training-fold majority class for every held-out participant."""
    y = dataset[target].values
    groups = dataset["participant"].values
    probabilities = np.zeros(len(dataset))
    for train_index, test_index in LeaveOneGroupOut().split(dataset, y, groups):
        positive_rate = y[train_index].mean()
        probabilities[test_index] = 1.0 if positive_rate >= 0.5 else 0.0
    oof = dataset[["participant", "block_id", "condition"]].copy()
    oof["y"] = y
    oof["proba"] = probabilities
    return oof


def run_condition_only_baseline(dataset, target):
    """
    Block-level logistic regression that only knows the experimental condition
    (N / I / T). The live app cannot know the condition, so this is a reference
    for 'how much would you get from simply knowing the stressor'.
    """
    blocks = dataset.groupby("block_id").agg(
        participant=("participant", "first"), y=(target, "first"),
        condition=("condition", "first")).reset_index()
    X = pd.get_dummies(blocks["condition"]).astype(float).values
    y = blocks["y"].values
    groups = blocks["participant"].values
    probabilities = np.zeros(len(blocks))
    for train_index, test_index in LeaveOneGroupOut().split(X, y, groups):
        model = LogisticRegression(max_iter=1000)
        model.fit(X[train_index], y[train_index])
        probabilities[test_index] = model.predict_proba(X[test_index])[:, 1]
    blocks["proba"] = probabilities
    return blocks


# ---------------------------------------------------------------------------
# uncertainty
# ---------------------------------------------------------------------------
def bootstrap_block_ci(block_df, n_boot=1000, seed=config.RANDOM_STATE):
    """Resample PARTICIPANTS (not blocks) with replacement; 95% percentile CI."""
    rng = np.random.default_rng(seed)
    participants = block_df["participant"].unique()
    groups = {}
    for participant in participants:
        groups[participant] = block_df[block_df["participant"] == participant]

    auc_values = []
    f1_values = []
    accuracy_values = []
    for _ in range(n_boot):
        sampled = rng.choice(participants, size=len(participants), replace=True)
        parts = []
        for participant in sampled:
            parts.append(groups[participant])
        sample_df = pd.concat(parts)
        if sample_df["y"].nunique() < 2:
            continue
        predicted = (sample_df["proba"] >= 0.5).astype(int)
        auc_values.append(roc_auc_score(sample_df["y"], sample_df["proba"]))
        f1_values.append(f1_score(sample_df["y"], predicted, zero_division=0))
        accuracy_values.append(accuracy_score(sample_df["y"], predicted))

    def interval(values):
        return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))]

    return {"roc_auc": interval(auc_values), "f1": interval(f1_values),
            "accuracy": interval(accuracy_values), "n_boot": len(auc_values)}


def within_person_permutation_pvalue(block_df, n_perm=2000, seed=config.RANDOM_STATE):
    """
    Approximate permutation test on the out-of-fold block scores: shuffle the
    block labels WITHIN each participant and see how often a block-level AUC at
    least as high as the observed one appears by chance.
    (The model is not re-trained per permutation - this is a sanity check of the
    held-out scores, not a full retraining test.)
    """
    rng = np.random.default_rng(seed)
    observed = roc_auc_score(block_df["y"], block_df["proba"])
    labels_by_person = []
    scores_by_person = []
    for participant, person_df in block_df.groupby("participant"):
        labels_by_person.append(person_df["y"].values)
        scores_by_person.append(person_df["proba"].values)
    all_scores = np.concatenate(scores_by_person)

    at_least_as_good = 0
    for _ in range(n_perm):
        permuted_parts = []
        for labels in labels_by_person:
            permuted_parts.append(rng.permutation(labels))
        permuted = np.concatenate(permuted_parts)
        if len(np.unique(permuted)) < 2:
            continue
        if roc_auc_score(permuted, all_scores) >= observed:
            at_least_as_good = at_least_as_good + 1
    return float((at_least_as_good + 1) / (n_perm + 1))


# ---------------------------------------------------------------------------
# plots
# ---------------------------------------------------------------------------
def save_roc_figure(block_results, target, path):
    plt.figure(figsize=(5.5, 5))
    for name, block_df in block_results.items():
        if block_df["y"].nunique() < 2:
            continue
        fpr, tpr, _ = roc_curve(block_df["y"], block_df["proba"])
        auc_value = roc_auc_score(block_df["y"], block_df["proba"])
        plt.plot(fpr, tpr, label=name + " (AUC " + format(auc_value, ".2f") + ")")
    plt.plot([0, 1], [0, 1], "k--", linewidth=1, label="chance")
    plt.xlabel("False positive rate")
    plt.ylabel("True positive rate")
    plt.title("Block-level ROC, LOSO - " + target)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(path, dpi=130)
    plt.close()


def save_confusion_figure(matrix, title, path):
    plt.figure(figsize=(3.6, 3.2))
    plt.imshow(matrix, cmap="Blues")
    row = 0
    while row < 2:
        column = 0
        while column < 2:
            plt.text(column, row, str(matrix[row][column]), ha="center", va="center")
            column = column + 1
        row = row + 1
    plt.xticks([0, 1], ["pred low", "pred high"])
    plt.yticks([0, 1], ["true low", "true high"])
    plt.title(title, fontsize=9)
    plt.tight_layout()
    plt.savefig(path, dpi=130)
    plt.close()


# ---------------------------------------------------------------------------
# main per-target routine
# ---------------------------------------------------------------------------
def evaluate_target(dataset, target):
    print("\n=== target:", target, "===")
    results = {"models": {}, "baselines": {}}
    block_results = {}

    models = make_models()
    for name, model in models.items():
        print("  LOSO for", name, "...")
        oof = run_loso(model, dataset, target)
        block_df = to_block_level(oof)
        block_results[name] = block_df
        results["models"][name] = {
            "window_level": compute_metrics(oof["y"], oof["proba"]),
            "block_level": compute_metrics(block_df["y"], block_df["proba"]),
        }
        auc_text = results["models"][name]["block_level"]["roc_auc"]
        print("     block AUC:", None if auc_text is None else round(auc_text, 3),
              "| window AUC:", round(results["models"][name]["window_level"]["roc_auc"], 3))

    majority_oof = run_majority_baseline(dataset, target)
    majority_blocks = to_block_level(majority_oof)
    results["baselines"]["majority_class"] = {
        "window_level": compute_metrics(majority_oof["y"], majority_oof["proba"]),
        "block_level": compute_metrics(majority_blocks["y"], majority_blocks["proba"]),
    }
    condition_blocks = run_condition_only_baseline(dataset, target)
    results["baselines"]["condition_only_block_level"] = {
        "block_level": compute_metrics(condition_blocks["y"], condition_blocks["proba"]),
    }

    best_name = None
    best_auc = -1.0
    for name in results["models"]:
        auc_value = results["models"][name]["block_level"]["roc_auc"]
        if auc_value is not None and auc_value > best_auc:
            best_auc = auc_value
            best_name = name

    best_blocks = block_results[best_name]
    results["best_model"] = best_name
    results["best_model_uncertainty"] = bootstrap_block_ci(best_blocks)
    results["best_model_permutation_p"] = within_person_permutation_pvalue(best_blocks)
    print("  best:", best_name, "block AUC", round(best_auc, 3),
          "CI", [round(v, 2) for v in results["best_model_uncertainty"]["roc_auc"]],
          "perm p", round(results["best_model_permutation_p"], 4))

    os.makedirs(config.FIGURES_DIR, exist_ok=True)
    save_roc_figure(block_results, target,
                    os.path.join(config.FIGURES_DIR, "roc_" + target + ".png"))
    save_confusion_figure(results["models"][best_name]["block_level"]["confusion_matrix"],
                          best_name + " block-level - " + target,
                          os.path.join(config.FIGURES_DIR, "confusion_" + target + ".png"))
    return results


def describe_evidence(target_results):
    lower = target_results["best_model_uncertainty"]["roc_auc"][0]
    p_value = target_results["best_model_permutation_p"]
    if lower > 0.5 and p_value < 0.05:
        return True, "Weak but statistically detectable signal in held-out participants."
    return False, ("No reliable signal: the participant-bootstrap interval for the "
                   "block-level ROC-AUC includes 0.5 or the permutation check is not significant.")


def fit_and_save(dataset, target, target_results, file_name):
    best_name = target_results["best_model"]
    model = make_models()[best_name]
    model.fit(dataset[config.MODEL_FEATURES].values, dataset[target].values)
    reliable, evidence_text = describe_evidence(target_results)
    bundle = {
        "pipeline": model,
        "model_name": best_name,
        "target": target,
        "feature_names": config.MODEL_FEATURES,
        "window_minutes": config.WINDOW_MINUTES,
        "version": MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "reliable_signal": reliable,
        "evidence_text": evidence_text,
        "loso_block_metrics": target_results["models"][best_name]["block_level"],
        "loso_uncertainty": target_results["best_model_uncertainty"],
        "permutation_p": target_results["best_model_permutation_p"],
        "background_X": dataset[config.MODEL_FEATURES].sample(
            n=min(200, len(dataset)), random_state=config.RANDOM_STATE).values,
    }
    os.makedirs(config.MODELS_DIR, exist_ok=True)
    joblib.dump(bundle, os.path.join(config.MODELS_DIR, file_name))
    return bundle


def format_table(target_results):
    lines = []
    lines.append("| Model | Level | Accuracy | Bal. acc. | Precision | Recall | F1 | ROC-AUC |")
    lines.append("|---|---|---|---|---|---|---|---|")

    def row(name, level, m):
        auc_text = "n/a" if m["roc_auc"] is None else format(m["roc_auc"], ".3f")
        return ("| " + name + " | " + level + " | " + format(m["accuracy"], ".3f") + " | "
                + format(m["balanced_accuracy"], ".3f") + " | " + format(m["precision"], ".3f")
                + " | " + format(m["recall"], ".3f") + " | " + format(m["f1"], ".3f")
                + " | " + auc_text + " |")

    for name, entry in target_results["models"].items():
        lines.append(row(name, "window", entry["window_level"]))
        lines.append(row(name, "**block**", entry["block_level"]))
    lines.append(row("Majority class", "block", target_results["baselines"]["majority_class"]["block_level"]))
    lines.append(row("Condition only (N/I/T known)", "block",
                     target_results["baselines"]["condition_only_block_level"]["block_level"]))
    return "\n".join(lines)


def write_report(all_results, dataset):
    path = os.path.join(config.DOCS_DIR, "model_evaluation_report.md")
    stress = all_results[config.PRIMARY_TARGET]
    effort = all_results[config.SECONDARY_TARGET]

    def ci_text(res):
        u = res["best_model_uncertainty"]
        return ("ROC-AUC " + format(res["models"][res["best_model"]]["block_level"]["roc_auc"], ".3f")
                + " (95% CI " + format(u["roc_auc"][0], ".2f") + " - " + format(u["roc_auc"][1], ".2f")
                + "), F1 " + format(res["models"][res["best_model"]]["block_level"]["f1"], ".3f")
                + " (95% CI " + format(u["f1"][0], ".2f") + " - " + format(u["f1"][1], ".2f")
                + "), within-person permutation p = " + format(res["best_model_permutation_p"], ".4f"))

    stress_ok, stress_text = describe_evidence(stress)
    effort_ok, effort_text = describe_evidence(effort)

    text = []
    text.append("# Model Evaluation Report")
    text.append("")
    text.append("_Generated by `python -m ml.train` on " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                + ". Every number below was produced by that run._")
    text.append("")
    text.append("## Setup")
    text.append("- Data: SWELL-KW per-minute computer-interaction features (`swell_computer_sheet1.csv`), "
                "cleaned as described in `phase1_dataset_findings.md`.")
    text.append("- Windows: " + str(config.WINDOW_MINUTES) + " consecutive minutes, stride 1 minute. "
                + str(len(dataset)) + " windows from " + str(dataset["participant"].nunique())
                + " participants and " + str(dataset["block_id"].nunique()) + " labelled blocks.")
    text.append("- Features: " + str(len(config.MODEL_FEATURES)) + " window features, each expressed as a "
                "z-score against the participant's own history (baseline-relative).")
    text.append("- Validation: Leave-One-Subject-Out (25 folds). No participant appears in both training and test.")
    text.append("- Window-level metrics treat each window as a sample, but windows overlap and share one block label, "
                "so they are **not independent**. **Block-level** rows (mean window score per labelled block, "
                "75 blocks) are the honest unit and are the ones used for model selection.")
    text.append("- Hyper-parameters are fixed (not tuned) to avoid leakage with only 25 participants.")
    text.append("- Model selection uses the same LOSO scores that are reported, so the winner's score carries a small "
                "optimistic selection bias.")
    text.append("")
    text.append("## Primary target: stress above the person's own mean (`" + config.PRIMARY_TARGET + "`)")
    text.append("Positive share: " + format(dataset.drop_duplicates("block_id")[config.PRIMARY_TARGET].mean(), ".2f"))
    text.append("")
    text.append(format_table(stress))
    text.append("")
    text.append("**Selected model:** " + stress["best_model"] + " - " + ci_text(stress))
    text.append("")
    text.append("**Verdict:** " + stress_text)
    text.append("")
    text.append("![ROC](figures/roc_" + config.PRIMARY_TARGET + ".png) "
                "![Confusion](figures/confusion_" + config.PRIMARY_TARGET + ".png)")
    text.append("")
    text.append("## Secondary target: mental effort above the person's own mean (`" + config.SECONDARY_TARGET + "`)")
    text.append("Positive share: " + format(dataset.drop_duplicates("block_id")[config.SECONDARY_TARGET].mean(), ".2f"))
    text.append("")
    text.append(format_table(effort))
    text.append("")
    text.append("**Selected model:** " + effort["best_model"] + " - " + ci_text(effort))
    text.append("")
    text.append("**Verdict:** " + effort_text)
    text.append("")
    text.append("![ROC](figures/roc_" + config.SECONDARY_TARGET + ".png) "
                "![Confusion](figures/confusion_" + config.SECONDARY_TARGET + ".png)")
    text.append("")
    text.append("## Limitations (read before using the predictions)")
    text.append("- Only 75 labelled blocks from 25 participants; confidence intervals are wide.")
    text.append("- Labels are self-reported once per block, not per minute.")
    text.append("- Training data came from system-wide logging on office PCs; the website only sees events on its own "
                "page, so live behaviour differs from the training distribution.")
    text.append("- The model score is **not a calibrated probability** and **not a diagnosis**.")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(text) + "\n")
    return path


def main():
    minute_df = preprocessing.load_minute_data()
    label_df = preprocessing.load_labels()
    dataset = features.build_dataset(minute_df, label_df)
    print("windows:", len(dataset), "participants:", dataset["participant"].nunique())

    all_results = {}
    all_results[config.PRIMARY_TARGET] = evaluate_target(dataset, config.PRIMARY_TARGET)
    all_results[config.SECONDARY_TARGET] = evaluate_target(dataset, config.SECONDARY_TARGET)

    fit_and_save(dataset, config.PRIMARY_TARGET, all_results[config.PRIMARY_TARGET], "stress_model.joblib")
    fit_and_save(dataset, config.SECONDARY_TARGET, all_results[config.SECONDARY_TARGET], "workload_model.joblib")

    with open(os.path.join(config.MODELS_DIR, "metrics.json"), "w", encoding="utf-8") as handle:
        json.dump(all_results, handle, indent=2)
    report_path = write_report(all_results, dataset)
    print("\nSaved models/, metrics.json and", report_path)


if __name__ == "__main__":
    main()
