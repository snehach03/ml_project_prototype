# Phase 1 - SWELL-KW dataset findings

Source files examined: `swell_computer_sheet1.csv`, `swell_computer_sheet3_csv.csv`,
`Questionnaire_Blok_Results_final_-_performance_added.tab`, `SWELL-KW - overview available data.tab`,
one raw uLog XML (`a_pp10_c1_uLog_...xml`), the dataset manual and the questionnaire PDF.
Re-run the audit with `python ml/phase1_explore.py`.

## Structure
- 25 participants (PP1-PP25), 3 task blocks each: **N** neutral, **I** email interruptions, **T** time pressure
  (order differs by participant). Every block starts with ~6 minutes of relaxation (**R**), which is not labelled.
- `swell_computer_sheet1.csv`: one row per participant-minute, 16 uLog counters (`SnMouseAct`, `SnKeyStrokes`,
  `SnErrorKeys`, `SnAppChange`, ...). 3,139 rows -> 2,655 usable non-relax minutes.
- Questionnaire file: one row per participant-block with a 0-10 stress slider, RSME mental effort, NASA-TLX scales
  and SAM ratings. 81 labelled blocks, of which 75 (25 participants x 3) have computer logs; pilots SP and MP do not.
- Raw uLog XML: only one participant-block was supplied (4,770 events, millisecond timestamps). Not usable for training.

## Data quality issues and how they were handled
| Issue | Handling |
|---|---|
| `swell_computer_sheet3_csv.csv`: `SnMouseDistance` on a ~1e15 scale, 31 NaNs, 1 extra row; other 15 features identical to sheet1 | sheet1 used as source of truth |
| 999 in every `Sn*` column on 31 rows (PP11 block 3, PP16 block 2) = failed recording | rows removed |
| `#VALUE!` in two `SnMouseDistance` cells | rows removed |
| Two empty trailing columns in sheet1 | dropped |
| Questionnaire has blank/summary rows | filtered to rows with Condition in N/I/T |
| Relax-phase minutes have no questionnaire label | excluded |
| Gaps in the minute log (missing minutes) | windows spanning more than 7 minutes are skipped |

## Labels
- Experimental condition is **not** ground-truth stress: mean stress was N 2.89, I 3.16, T 3.84 and time pressure raised
  stress for only 17 of 25 people compared with their neutral block.
- 65% of the variance in the stress slider is within-person, so personal baselines matter.
- Targets chosen: `stress_elevated` (stress above the participant's own mean over their 3 blocks, 53% positive) and
  `effort_high` (RSME above own mean, 45% positive).

## Limitations
- 75 labels in total; windows from one block share one label, so effective sample size is ~75, not 2,355.
- Self-report once per block, not per minute.
- uLog logged the entire computer; a website sees only its own page.
- 1-minute windows are almost never fully idle (1-2% of minutes), so idle time and inter-keystroke intervals cannot be
  learned from this table; the dashboard displays them but the model never uses them.
