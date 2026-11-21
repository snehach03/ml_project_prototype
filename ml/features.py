"""
Phase 2b - feature engineering.

Two stages:
  1. make_window_features()  : 5 consecutive minutes  -> 19 behavioural features
  2. make_relative_features(): features -> z-scores against the PERSON'S OWN
                               baseline (mean/std of the same feature over
                               that person's history)

The very same functions are used by the live backend, so training and
inference cannot drift apart.
"""

import numpy as np
import pandas as pd

from ml import config


def _slope(values):
    """Least-squares slope of values against 0..n-1 (0.0 if fewer than 2 points)."""
    n = len(values)
    if n < 2:
        return 0.0
    x_values = np.arange(n, dtype=float)
    y_values = np.asarray(values, dtype=float)
    x_mean = x_values.mean()
    y_mean = y_values.mean()
    numerator = ((x_values - x_mean) * (y_values - y_mean)).sum()
    denominator = ((x_values - x_mean) ** 2).sum()
    if denominator == 0:
        return 0.0
    return float(numerator / denominator)


def _safe_std(values):
    """Population-free sample std; 0.0 when only one value."""
    if len(values) < 2:
        return 0.0
    return float(np.std(values, ddof=1))


def _safe_ratio(numerator, denominator):
    if denominator <= 0:
        return 0.0
    return float(numerator / denominator)


def make_window_features(window):
    """
    window: DataFrame with one row per minute (columns = config.MINUTE_FIELDS).
    Returns a dict {feature_name: value} for config.WINDOW_FEATURES.
    """
    clicks = window["left_clicks"] + window["right_clicks"] + window["double_clicks"]

    active_minutes = 0
    row_index = 0
    while row_index < len(window):
        row = window.iloc[row_index]
        if row["keystrokes"] > 0 or row["mouse_act"] > 0:
            active_minutes = active_minutes + 1
        row_index = row_index + 1

    total_keys = float(window["keystrokes"].sum())

    features = {}
    features["keys_mean"] = float(window["keystrokes"].mean())
    features["keys_std"] = _safe_std(window["keystrokes"])
    features["chars_mean"] = float(window["chars"].mean())
    features["error_ratio"] = _safe_ratio(window["error_keys"].sum(), total_keys)
    features["special_ratio"] = _safe_ratio(window["special_keys"].sum(), total_keys)
    features["spaces_mean"] = float(window["spaces"].mean())
    features["direction_mean"] = float(window["direction_keys"].mean())
    features["mouse_act_mean"] = float(window["mouse_act"].mean())
    features["mouse_act_std"] = _safe_std(window["mouse_act"])
    features["mouse_dist_mean"] = float(window["mouse_distance"].mean())
    features["mouse_dist_std"] = _safe_std(window["mouse_distance"])
    features["clicks_mean"] = float(clicks.mean())
    features["wheel_mean"] = float(window["wheel"].mean())
    features["drag_mean"] = float(window["drags"].mean())
    features["app_change_mean"] = float(window["app_changes"].mean())
    features["tab_change_mean"] = float(window["tab_changes"].mean())
    features["active_share"] = float(active_minutes / len(window))
    features["keys_slope"] = _slope(window["keystrokes"].values)
    features["mouse_act_slope"] = _slope(window["mouse_act"].values)
    return features


def make_windows_for_sequence(minutes, timestamps=None, window_minutes=None):
    """
    Slide a window (stride = 1 minute) over ONE continuous sequence of minutes
    (one block in training, one session in the live app).

    Returns a list of dicts: window features + 'end_position' (row index of the
    last minute in the window). Windows spanning a logging gap are skipped.
    """
    if window_minutes is None:
        window_minutes = config.WINDOW_MINUTES

    results = []
    n_rows = len(minutes)
    start = 0
    while start + window_minutes <= n_rows:
        end = start + window_minutes
        too_long = False
        if timestamps is not None:
            span_seconds = (timestamps.iloc[end - 1] - timestamps.iloc[start]).total_seconds()
            if span_seconds > config.MAX_WINDOW_SPAN_MIN * 60:
                too_long = True
        if not too_long:
            window = minutes.iloc[start:end]
            row = make_window_features(window)
            row["end_position"] = end - 1
            results.append(row)
        start = start + 1
    return results


def build_training_windows(minute_df):
    """All windows for all participants/blocks, with identifiers."""
    all_rows = []
    grouped = minute_df.groupby(["participant", "block"], sort=True)
    for (participant, block), block_df in grouped:
        block_df = block_df.sort_values("ts").reset_index(drop=True)
        windows = make_windows_for_sequence(block_df[config.MINUTE_FIELDS], block_df["ts"])
        for row in windows:
            row["participant"] = participant
            row["block"] = block
            row["condition"] = block_df["condition"].iloc[0]
            all_rows.append(row)
    return pd.DataFrame(all_rows)


# ---------------------------------------------------------------------------
# Personal baseline
# ---------------------------------------------------------------------------
def compute_baseline(window_df):
    """
    window_df: DataFrame of window features (config.WINDOW_FEATURES columns) for
    ONE person. Returns {'mean': {...}, 'std': {...}, 'n_windows': int}.
    """
    baseline = {"mean": {}, "std": {}, "n_windows": int(len(window_df))}
    for name in config.WINDOW_FEATURES:
        baseline["mean"][name] = float(window_df[name].mean())
        baseline["std"][name] = _safe_std(window_df[name].values)
    return baseline


def to_relative(feature_dict, baseline):
    """z-score one window's features against a baseline. Returns {rel_name: z}."""
    relative = {}
    for name in config.WINDOW_FEATURES:
        std_value = baseline["std"][name]
        if std_value < config.EPSILON:
            std_value = 1.0
        relative["rel_" + name] = (feature_dict[name] - baseline["mean"][name]) / std_value
    return relative


def add_relative_features(window_df):
    """Training helper: attach rel_* columns using each participant's own windows."""
    parts = []
    for participant, person_df in window_df.groupby("participant", sort=True):
        baseline = compute_baseline(person_df)
        relative_rows = []
        row_index = 0
        while row_index < len(person_df):
            feature_dict = person_df.iloc[row_index][config.WINDOW_FEATURES].to_dict()
            relative_rows.append(to_relative(feature_dict, baseline))
            row_index = row_index + 1
        relative_df = pd.DataFrame(relative_rows, index=person_df.index)
        parts.append(pd.concat([person_df, relative_df], axis=1))
    return pd.concat(parts).sort_index()


def build_dataset(minute_df, label_df):
    """Windows + relative features + block labels. This is the model-ready table."""
    windows = build_training_windows(minute_df)
    windows = add_relative_features(windows)
    dataset = windows.merge(label_df, on=["participant", "block"], how="inner")
    dataset["block_id"] = dataset["participant"] + "_" + dataset["block"].astype(str)
    return dataset
