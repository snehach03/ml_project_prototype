"""
Phase 2a - loading and cleaning the SWELL-KW files.

Only the cleaning rules that Phase 1 proved necessary are applied:
  * the uLog sentinel value 999 means "recording failed"  -> row removed
  * '#VALUE!' cells in SnMouseDistance                   -> row removed
  * relax (R) minutes are not part of any labelled block -> removed
  * questionnaire file has blank / summary rows           -> removed
  * pilots SP and MP have labels but no logs              -> removed
"""

import numpy as np
import pandas as pd

from ml import config


def load_minute_data():
    """Return one row per (participant, block, minute) with cleaned numeric fields."""
    raw = pd.read_csv(config.COMPUTER_CSV)

    # two empty trailing columns exist in the export
    keep_columns = []
    for column_name in raw.columns:
        if not column_name.startswith("Unnamed"):
            keep_columns.append(column_name)
    raw = raw[keep_columns].copy()

    raw["SnMouseDistance"] = pd.to_numeric(raw["SnMouseDistance"], errors="coerce")

    sn_columns = list(config.SN_TO_MINUTE_FIELD.keys())
    for column_name in sn_columns:
        raw[column_name] = raw[column_name].replace(config.MISSING_SENTINEL, np.nan)

    raw = raw.rename(columns=config.SN_TO_MINUTE_FIELD)
    raw["participant"] = raw["PP"].str.replace("PP", "", regex=False)
    raw["block"] = raw["Blok"].astype(int)
    raw["condition"] = raw["Condition"]
    raw["ts"] = pd.to_datetime(raw["timestamp"].str[:15], format="%Y%m%dT%H%M%S")

    before = len(raw)
    raw = raw.dropna(subset=config.MINUTE_FIELDS)
    raw = raw[raw["condition"] != "R"]
    raw = raw.sort_values(["participant", "block", "ts"]).reset_index(drop=True)

    columns = ["participant", "block", "condition", "ts"] + config.MINUTE_FIELDS
    cleaned = raw[columns].copy()
    cleaned.attrs["rows_before_cleaning"] = before
    return cleaned


def load_labels():
    """Return one row per labelled block with the two binary targets."""
    q = pd.read_csv(config.QUESTIONNAIRE_TAB, sep="\t")
    q = q[q["Condition"].isin(["N", "I", "T"])].copy()
    q["participant"] = q["PP"].astype(str).str.replace(r"\.0$", "", regex=True)
    q["block"] = q["Blok"].astype(int)
    q = q[~q["participant"].isin(["SP", "MP"])].copy()

    person_mean_stress = q.groupby("participant")["Stress"].transform("mean")
    person_mean_effort = q.groupby("participant")["MentalEffort"].transform("mean")

    q[config.PRIMARY_TARGET] = (q["Stress"] > person_mean_stress).astype(int)
    q[config.SECONDARY_TARGET] = (q["MentalEffort"] > person_mean_effort).astype(int)

    keep = [
        "participant", "block", "Condition", "Stress", "MentalEffort",
        config.PRIMARY_TARGET, config.SECONDARY_TARGET,
    ]
    return q[keep].rename(columns={"Condition": "label_condition"}).reset_index(drop=True)
