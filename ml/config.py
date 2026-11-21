"""
Central configuration for the ML pipeline.

Everything that both the training code and the live backend must agree on
(feature names, window length, column mapping) lives in this one file.
"""

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(PROJECT_ROOT, "dataset")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
DOCS_DIR = os.path.join(PROJECT_ROOT, "documentation")
FIGURES_DIR = os.path.join(DOCS_DIR, "figures")

COMPUTER_CSV = os.path.join(DATASET_DIR, "swell_computer_sheet1.csv")
QUESTIONNAIRE_TAB = os.path.join(
    DATASET_DIR, "Questionnaire_Blok_Results_final_-_performance_added.tab"
)

# --------------------------------------------------------------------------
# Raw per-minute columns (SWELL-KW uLog names) -> names used in this project.
# The right-hand names are ALSO the names the browser tracker sends.
# --------------------------------------------------------------------------
SN_TO_MINUTE_FIELD = {
    "SnMouseAct": "mouse_act",
    "SnLeftClicked": "left_clicks",
    "SnRightClicked": "right_clicks",
    "SnDoubleClicked": "double_clicks",
    "SnWheel": "wheel",
    "SnDragged": "drags",
    "SnMouseDistance": "mouse_distance",
    "SnKeyStrokes": "keystrokes",
    "SnChars": "chars",
    "SnSpecialKeys": "special_keys",
    "SnDirectionKeys": "direction_keys",
    "SnErrorKeys": "error_keys",
    "SnShortcutKeys": "shortcut_keys",
    "SnSpaces": "spaces",
    "SnAppChange": "app_changes",
    "SnTabfocusChange": "tab_changes",
}
MINUTE_FIELDS = list(SN_TO_MINUTE_FIELD.values())

# Fields the browser can show on the dashboard but that the model never sees
# (they cannot be learned from the per-minute training data).
DISPLAY_ONLY_FIELDS = ["iki_mean_ms", "iki_std_ms", "idle_seconds"]

MISSING_SENTINEL = 999     # uLog marker for "recording failed"
WINDOW_MINUTES = 5         # rolling window length
MAX_WINDOW_SPAN_MIN = 7    # skip windows that straddle a logging gap
MIN_BASELINE_WINDOWS = 10  # windows needed before a personal baseline is trusted
EPSILON = 1e-9

# --------------------------------------------------------------------------
# Window-level features (computed from WINDOW_MINUTES consecutive minutes)
# --------------------------------------------------------------------------
WINDOW_FEATURES = [
    "keys_mean",
    "keys_std",
    "chars_mean",
    "error_ratio",
    "special_ratio",
    "spaces_mean",
    "direction_mean",
    "mouse_act_mean",
    "mouse_act_std",
    "mouse_dist_mean",
    "mouse_dist_std",
    "clicks_mean",
    "wheel_mean",
    "drag_mean",
    "app_change_mean",
    "tab_change_mean",
    "active_share",
    "keys_slope",
    "mouse_act_slope",
]

# Model input names = baseline-relative (z-score vs the person's own history)
MODEL_FEATURES = ["rel_" + name for name in WINDOW_FEATURES]

FEATURE_DESCRIPTIONS = {
    "keys_mean": "typing volume (keystrokes per minute)",
    "keys_std": "variability of typing volume between minutes",
    "chars_mean": "printable characters typed per minute",
    "error_ratio": "share of keystrokes that were corrections (backspace/delete)",
    "special_ratio": "share of keystrokes that were special keys",
    "spaces_mean": "space-bar presses per minute (a proxy for word rate)",
    "direction_mean": "arrow-key presses per minute",
    "mouse_act_mean": "mouse activity events per minute",
    "mouse_act_std": "variability of mouse activity between minutes",
    "mouse_dist_mean": "distance the cursor travelled per minute",
    "mouse_dist_std": "variability of cursor distance between minutes",
    "clicks_mean": "mouse clicks per minute",
    "wheel_mean": "scroll-wheel events per minute",
    "drag_mean": "mouse drag events per minute",
    "app_change_mean": "window/application focus changes per minute",
    "tab_change_mean": "tab or page visibility changes per minute",
    "active_share": "share of minutes with any keyboard or mouse activity",
    "keys_slope": "trend of typing volume over the window (rising/falling)",
    "mouse_act_slope": "trend of mouse activity over the window (rising/falling)",
}

# --------------------------------------------------------------------------
# Targets (see documentation/phase1 findings)
# --------------------------------------------------------------------------
PRIMARY_TARGET = "stress_elevated"   # Stress slider above the person's own mean
SECONDARY_TARGET = "effort_high"     # RSME mental effort above the person's own mean
RANDOM_STATE = 42
