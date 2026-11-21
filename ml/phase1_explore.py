"""
Phase 1 - SWELL-KW dataset audit (computer-interaction data + questionnaire labels).

Run from the project root:
    python ml/phase1_explore.py

Expected files in dataset/:
    swell_computer_sheet1.csv
    swell_computer_sheet3_csv.csv
    Questionnaire_Blok_Results_final_-_performance_added.tab

This script only INSPECTS data. It trains nothing and writes nothing except
printing a report to the console.
"""

import os
import numpy as np
import pandas as pd

DATASET_DIR = "dataset"
SHEET1_PATH = os.path.join(DATASET_DIR, "swell_computer_sheet1.csv")
SHEET3_PATH = os.path.join(DATASET_DIR, "swell_computer_sheet3_csv.csv")
QUESTIONNAIRE_PATH = os.path.join(
    DATASET_DIR, "Questionnaire_Blok_Results_final_-_performance_added.tab"
)

MISSING_SENTINEL = 999  # uLog failed-recording marker found in every Sn* column
KEY_COLUMNS = ["PP", "Blok", "timestamp"]


def print_title(text):
    print("")
    print("=" * 78)
    print(text)
    print("=" * 78)


def get_count_columns(df):
    """Return all per-minute interaction columns (they all start with 'Sn')."""
    columns = []
    for column_name in df.columns:
        if column_name.startswith("Sn"):
            columns.append(column_name)
    return columns


def load_sheet1():
    df = pd.read_csv(SHEET1_PATH)
    # The file has two empty trailing columns ('Unnamed: 20', 'Unnamed: 21').
    keep_columns = []
    for column_name in df.columns:
        if not column_name.startswith("Unnamed"):
            keep_columns.append(column_name)
    df = df[keep_columns].copy()
    # SnMouseDistance is stored as text because 2 cells contain '#VALUE!'.
    df["SnMouseDistance"] = pd.to_numeric(df["SnMouseDistance"], errors="coerce")
    return df


def load_sheet3():
    return pd.read_csv(SHEET3_PATH)


def load_questionnaire():
    q = pd.read_csv(QUESTIONNAIRE_PATH, sep="\t")
    # The file contains blank rows and summary rows at the bottom.
    # Real rows always have a Condition of N, I or T.
    q = q[q["Condition"].isin(["N", "I", "T"])].copy()
    q["PP"] = q["PP"].astype(str).str.replace(r"\.0$", "", regex=True)
    q["Blok"] = q["Blok"].astype(int)
    return q


def audit_sheets(sheet1, sheet3):
    print_title("1. sheet1 vs sheet3")
    print("sheet1 shape:", sheet1.shape)
    print("sheet3 shape:", sheet3.shape)

    merged = sheet1.merge(
        sheet3, on=KEY_COLUMNS, how="outer", suffixes=("_s1", "_s3"), indicator=True
    )
    print("Row match status:", merged["_merge"].value_counts().to_dict())

    only_sheet3 = merged[merged["_merge"] == "right_only"]
    print("Rows only in sheet3:")
    print(only_sheet3[KEY_COLUMNS + ["Condition_s3"]])

    both = merged[merged["_merge"] == "both"]
    count_columns = get_count_columns(sheet1)
    for column_name in count_columns:
        if column_name == "SnMouseDistance":
            continue
        first = both[column_name + "_s1"].astype(float)
        third = both[column_name + "_s3"].astype(float)
        number_of_differences = int(((first - third).abs() > 1e-9).sum())
        print(column_name, "differences between sheets:", number_of_differences)

    print("")
    print("sheet3 SnMouseDistance summary (values around 1e15 -> corrupted scale):")
    print(sheet3["SnMouseDistance"].describe())
    print("Conclusion: use sheet1 as the source of truth.")


def audit_missing_values(sheet1):
    print_title("2. Missing values and sentinel 999")
    count_columns = get_count_columns(sheet1)
    sentinel_mask = sheet1[count_columns] == MISSING_SENTINEL
    rows_with_sentinel = sentinel_mask.any(axis=1)
    print("Rows containing 999:", int(rows_with_sentinel.sum()))
    print(sheet1[rows_with_sentinel].groupby(["PP", "Blok", "Condition"]).size())
    print("'#VALUE!' cells in SnMouseDistance (now NaN):",
          int(sheet1["SnMouseDistance"].isna().sum()))


def audit_structure(sheet1):
    print_title("3. Structure")
    print("Participants:", sheet1["PP"].nunique())
    print("Rows per (Blok, Condition):")
    print(sheet1.groupby(["Blok", "Condition"]).size())
    print("")
    print("Relax (R) minutes per block, per participant:")
    relax_rows = sheet1[sheet1["Condition"] == "R"]
    print(relax_rows.groupby(["PP", "Blok"]).size().describe())
    print("")
    print("Minutes per participant-block (all conditions):")
    print(sheet1.groupby(["PP", "Blok"]).size().describe())


def audit_distributions(sheet1):
    print_title("4. Distributions of per-minute features (999 treated as NaN)")
    count_columns = get_count_columns(sheet1)
    clean = sheet1.copy()
    for column_name in count_columns:
        clean[column_name] = clean[column_name].replace(MISSING_SENTINEL, np.nan)
    print(clean[count_columns].describe().T.round(2))

    working = clean[clean["Condition"] != "R"]
    zero_activity_count = 0
    for index in working.index:
        row_values = working.loc[index, count_columns]
        if (row_values.fillna(0) == 0).all():
            zero_activity_count = zero_activity_count + 1
    share = zero_activity_count / len(working)
    print("")
    print("Share of non-relax minutes with ZERO activity:", round(share, 3))
    print("Meaning: 1-minute windows almost never look 'idle', so idle time")
    print("cannot be learned reliably from this minute-level data.")


def audit_labels(questionnaire):
    print_title("5. Questionnaire labels")
    print("Labelled blocks (incl. pilots SP, MP):", len(questionnaire))
    print("Participants:", questionnaire["PP"].nunique())
    print("Pilots SP and MP have labels but NO computer logs -> excluded.")

    labelled = questionnaire[~questionnaire["PP"].isin(["SP", "MP"])].copy()
    print("Usable labelled blocks:", len(labelled))

    print("")
    print("Mean Stress / MentalEffort by condition:")
    print(labelled.groupby("Condition")[["Stress", "MentalEffort"]].mean().round(2))

    print("")
    print("Stress (0-10 slider) summary:")
    print(labelled["Stress"].describe().round(2))

    median_value = labelled["Stress"].median()
    print("")
    print("Positive-class share if Stress > median (", median_value, "):",
          round((labelled["Stress"] > median_value).mean(), 2))
    print("Positive-class share if Stress >= 5:",
          round((labelled["Stress"] >= 5).mean(), 2))

    person_mean = labelled.groupby("PP")["Stress"].transform("mean")
    print("Positive-class share if Stress > the person's own mean:",
          round((labelled["Stress"] > person_mean).mean(), 2))

    for target in ["Stress", "MentalEffort", "TemporalDemand", "Frustration"]:
        total_variance = labelled[target].var()
        person_mean = labelled.groupby("PP")[target].transform("mean")
        within_variance = (labelled[target] - person_mean).var()
        within_variance = within_variance * len(labelled) / (len(labelled) - labelled["PP"].nunique())
        print(target, "within-person share of variance:",
              round(within_variance / total_variance, 2))

    print("")
    pivot = labelled.pivot(index="PP", columns="Condition", values="Stress")
    print("Participants with Stress(T) > Stress(N):", int((pivot["T"] > pivot["N"]).sum()), "of", len(pivot))
    print("Participants with Stress(T) > Stress(I):", int((pivot["T"] > pivot["I"]).sum()), "of", len(pivot))
    print("Participants with Stress(I) > Stress(N):", int((pivot["I"] > pivot["N"]).sum()), "of", len(pivot))


def check_join(sheet1, questionnaire):
    print_title("6. Join check: computer blocks vs questionnaire blocks")
    work = sheet1[sheet1["Condition"] != "R"].copy()
    work["PP"] = work["PP"].str.replace("PP", "", regex=False)

    block_conditions = work.groupby(["PP", "Blok"])["Condition"].agg(lambda x: x.mode()[0]).reset_index()
    joined = block_conditions.merge(
        questionnaire[["PP", "Blok", "Condition"]],
        on=["PP", "Blok"], how="inner", suffixes=("_computer", "_questionnaire"),
    )
    mismatches = joined[joined["Condition_computer"] != joined["Condition_questionnaire"]]
    print("Joined blocks:", len(joined))
    print("Condition mismatches:", len(mismatches))


def main():
    sheet1 = load_sheet1()
    sheet3 = load_sheet3()
    questionnaire = load_questionnaire()

    audit_sheets(sheet1, sheet3)
    audit_missing_values(sheet1)
    audit_structure(sheet1)
    audit_distributions(sheet1)
    audit_labels(questionnaire)
    check_join(sheet1, questionnaire)


if __name__ == "__main__":
    main()
