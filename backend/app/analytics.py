"""Behavioural analytics computed from stored per-minute counters (no ML here)."""

import numpy as np


def _clicks(row):
    return row.left_clicks + row.right_clicks + row.double_clicks


def _error_ratio(row):
    if row.keystrokes <= 0:
        return 0.0
    return float(row.error_keys / row.keystrokes)


def _switches(row):
    return row.app_changes + row.tab_changes


def minute_series(metrics):
    series = []
    for row in metrics:
        series.append({
            "minute": row.minute_index + 1,
            "typing_speed_cpm": float(row.chars),          # characters per minute
            "keystrokes": float(row.keystrokes),
            "backspace_ratio": _error_ratio(row),
            "mouse_activity": float(row.mouse_act),
            "mouse_distance": float(row.mouse_distance),
            "clicks": float(_clicks(row)),
            "scroll_events": float(row.wheel),
            "idle_seconds": None if row.idle_seconds is None else float(row.idle_seconds),
            "switches": float(_switches(row)),
            "iki_mean_ms": None if row.iki_mean_ms is None else float(row.iki_mean_ms),
            "iki_std_ms": None if row.iki_std_ms is None else float(row.iki_std_ms),
        })
    return series


def _mean(values):
    if len(values) == 0:
        return 0.0
    return float(np.mean(values))


def _cv(values):
    """Coefficient of variation (std / mean); 0 when mean is 0."""
    if len(values) < 2:
        return 0.0
    mean_value = float(np.mean(values))
    if mean_value == 0:
        return 0.0
    return float(np.std(values, ddof=1) / mean_value)


def _percent_change(before, after):
    if before == 0:
        return None
    return float((after - before) / before * 100.0)


def variability(series):
    return {
        "typing_cv": _cv([p["keystrokes"] for p in series]),
        "mouse_activity_cv": _cv([p["mouse_activity"] for p in series]),
        "mouse_distance_cv": _cv([p["mouse_distance"] for p in series]),
    }


def pattern_changes(series):
    """First half vs second half of the session."""
    if len(series) < 6:
        return None
    middle = len(series) // 2
    first = series[:middle]
    second = series[middle:]
    result = {}
    for key in ["keystrokes", "mouse_activity", "clicks", "scroll_events", "switches", "backspace_ratio"]:
        before = _mean([p[key] for p in first])
        after = _mean([p[key] for p in second])
        result[key] = {"first_half": before, "second_half": after, "percent_change": _percent_change(before, after)}
    return result


def history_means(history_rows):
    """Per-minute means over the user's earlier sessions (None if there are none)."""
    if len(history_rows) == 0:
        return None
    series = minute_series(history_rows)
    return {
        "keystrokes": _mean([p["keystrokes"] for p in series]),
        "typing_speed_cpm": _mean([p["typing_speed_cpm"] for p in series]),
        "backspace_ratio": _mean([p["backspace_ratio"] for p in series]),
        "mouse_activity": _mean([p["mouse_activity"] for p in series]),
        "mouse_distance": _mean([p["mouse_distance"] for p in series]),
        "clicks": _mean([p["clicks"] for p in series]),
        "scroll_events": _mean([p["scroll_events"] for p in series]),
        "switches": _mean([p["switches"] for p in series]),
        "minutes": len(series),
    }


def versus_baseline(series, history):
    if history is None or len(series) == 0:
        return None
    result = {}
    for key in ["keystrokes", "typing_speed_cpm", "backspace_ratio", "mouse_activity",
                "mouse_distance", "clicks", "scroll_events", "switches"]:
        session_mean = _mean([p[key] for p in series])
        result[key] = {"session_mean": session_mean, "history_mean": history[key],
                       "percent_difference": _percent_change(history[key], session_mean)}
    return result


def summary(series):
    if len(series) == 0:
        return {"minutes": 0}
    idle_values = []
    for point in series:
        if point["idle_seconds"] is not None:
            idle_values.append(point["idle_seconds"])
    return {
        "minutes": len(series),
        "avg_typing_speed_cpm": _mean([p["typing_speed_cpm"] for p in series]),
        "avg_keystrokes_per_min": _mean([p["keystrokes"] for p in series]),
        "avg_backspace_ratio": _mean([p["backspace_ratio"] for p in series]),
        "avg_mouse_distance_per_min": _mean([p["mouse_distance"] for p in series]),
        "total_clicks": float(sum(p["clicks"] for p in series)),
        "total_scroll_events": float(sum(p["scroll_events"] for p in series)),
        "total_switches": float(sum(p["switches"] for p in series)),
        "avg_idle_seconds_per_min": _mean(idle_values) if len(idle_values) > 0 else None,
    }
