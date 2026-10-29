# VALIDATION_LOG.md

Evidence register for CanopyGuard-AI. One row per result that a paper claim
rests on. Created 2026-10-29.

**Purpose.** `PROJECT_STATUS.md` records what work exists. This file records
what has actually been *checked*, by whom, against what evidence. A result may
appear "done" in the action plan and still be unvalidated here. That is the
normal state, not an error.

## Status vocabulary

These are not interchangeable. Every row must use exactly one.

| Status | Meaning |
| --- | --- |
| **Implemented** | Code runs and produces output. Nobody has checked the output. |
| **Tested** | Automated tests cover the code path. Says nothing about whether the science is right. |
| **Protocol-reproduced** | A second implementation of the documented protocol reproduces the numbers. Does not check the protocol against the data. |
| **Independently reviewed** | A person who did not author the work re-ran it from a clean checkout and signed the numbers. |
| **Scientifically validated** | Independently reviewed *and* the upstream inputs (labels, joins, flags) have themselves been checked. |
| **Blocked** | Cannot proceed until a named dependency clears. |
| **Not started** | — |

## Standing rule

No number enters a paper draft until its row here reads at least
**independently reviewed**, with a named human owner and a date.

---

## Register

### V1 — G1 noise floor, 2022-2023 seam
- **Status:** Implemented. Raw outputs recovered 2026-10-29 and independently checked.
- **Claim it supports:** LoD95(10 m) = 0.235 m; reference sigma 0.120 m; stable-cell fraction 0.936; co-registration shift 0.137 m.
- **Evidence:** Colab run 2026-09-23 (`MEMORY.md`); raw outputs supplied by Satvik 2026-10-29 and checked in `reports/a1_truth4_recovery_2026-10-29.md`. All six recorded headline figures reproduce exactly from the raw files. Hashes recorded in that report.
- **A1 is cleared** once the four files are placed in `data/processed/truth4/`.
- **Decay exponent resolved:** 0.054 and 0.107 are the same fit in two parameterizations — 0.054 with respect to cell count, 0.108 with respect to linear scale, exact factor of two, identical r2 (0.8619614) and coefficient (0.1508137). Neither is wrong. The benchmark must match the parameterization: 0.5 in cell-count space, 1.0 in scale space. Either way the error decays at 10.8% of the independent-error rate.
- **Unresolved:** the 0.158 figure in `configs/lidar.yaml` is not testable from these files. B2 is still required — this check identifies the numbers, it does not fit the error structure.
- **Pipeline validated 2026-10-29:** the 10 m floor was recomputed from the per-tile CHM rasters using this repo's own rules and reproduces 25,569 cells / sigma 0.120079 / mean -0.07996 / LoD95 0.235354 exactly. The implementation is correct.
- **0.158 is not reproducible** from any fit to `configs/lidar.yaml`. There is no third value. D1 is closed.
- **New issues raised:** see V11 (canopy-stratified floor), V12 (config/code disagreement on bias removal), V13 (GRSL letter not in version control), and the non-random tile admission in the A1 report Finding 5.

### V2 — Label archive, 2013-2022
- **Status:** Implemented. Hashes recorded.
- **Claim it supports:** 1,478,103 unique cells; 1,477,905 eligible after dropping 198 disputed overlaps.
- **Evidence:** `dvc.lock`, stage `label_quality_2013_2022`; `data/processed/labels_2013-2022_unique.npz` md5 `449032f5fcb1db0e54c9e455fe1b2cdf`.
- **Unresolved:** data exists only on one laptop. `dvc push` not done (item **A2**). A fresh clone cannot reproduce anything.

### V3 — ASPRS wire/tower classes absent
- **Status:** Implemented, single run.
- **Claim it supports:** classes 14 and 15 absent from all 120 inspected cells in both epochs; therefore no class filter can remove conductors.
- **Evidence:** `reports/wire_tower_label_check_2013-2022.md`.
- **Unresolved:** 120 cells is a small sample for an absolute "absent" claim. Either widen the sample or weaken the wording to the inspected set.

### V4 — W3 near-line enrichment of the tall tail
- **Status:** Implemented. **Not independently reviewed.**
- **Claim it supports:** enrichment 2.4x at 20 m rising monotonically to 10.2x at 45 m; 622 biologically impossible grass/shrub cells, 99.8% within 30 m, median 5 m; spike detector catches 0.1-0.3%.
- **Evidence:** `reports/w3_tall_tail_enrichment_2013-2022.md` + `.json`, run 2026-10-27, script `scripts/w3_tall_tail_enrichment.py`. Rules fixed before rates computed; whole-tile bootstrap, 2,000 draws, seed 42.
- **Unresolved:** item **B5** / GitHub issue #6 — Rehaan to re-run from a clean checkout. Until then this is an AI-run analysis that no second party has confirmed.
- **Known scope limit:** CEC transmission lines only. Distribution lines untested — see V8.

### V5 — G3 stage-one comparison
- **Status:** **Protocol-reproduced.** Not independently reviewed.
- **Claim it supports:** median-prior minus no-change = -0.1211 m [-0.1453, -0.0970] at 2 km blocks; stable across 1 km and 5 km.
- **Evidence:** `scripts/independent_g3_check.py`, run 2026-10-29. Second implementation from `configs/forecasting.yaml` and the evaluation modules, written without reading `growth_curve.py`'s comparison. All ten headline quantities match, both interval bounds to four decimal places.
- **Explicitly does NOT cover:** label construction, the vegetation join, the wire flags, the terrain join. All are upstream and untouched.
- **Unresolved:** a human rerun from the data by a non-author. This is **S1** and is the submission gate.

### V6 — L2 vegetation-map contribution
- **Status:** Protocol-reproduced, new result 2026-10-29.
- **Claim it supports:** a global constant prior recovers ~94% of the measured gain (0.1139 m of 0.1211 m at 2 km). Per-fold global median increment 0.462-0.478 m.
- **Consequence recorded:** the collinearity concern (Sonoma Veg Map partly built from 2013 LiDAR) is largely defused, but the result must stop being described as a "vegetation-map-class median prior". It is effectively "add 0.46 m".
- **Unresolved:** stage two still uses `vegetation_type` as a categorical feature; this check covers stage one only.

### V7 — E8 ECHOSAT benchmark
- **Status:** Implemented and reviewed against its preregistration.
- **Claim it supports:** MAE 3.951 m; mean signed error +2.475 m; ~4.3 m of canopy placed on 563,055 cells where LiDAR p95 < 2 m; 9.6 m short above 30 m; bias flat at 2.48 m while the random part decays at exponent 0.33.
- **Evidence:** PR #21, branch `codex/e8-benchmark`, git revision `c260642`; `reports/e8_echosat_benchmark_2022.md`; review in `reports/review_e8_benchmark_2026-10-29.md`.
- **Unresolved:** three additions outstanding — re-bin by product height as well as by reference, stratify by distance to line, report compression as a regression slope.

### V8 — Distribution-line enrichment
- **Status:** **Not started.** Item **B4** / **W4**, owner Satvik.
- **Why it is not cosmetic:** see `reports/task_spec_b4_distribution_lines_2026-10-29.md`. Distribution conductors sit at roughly 10-15 m, inside the bulk of the height distribution, not in the tall tail. If they contaminate the 10-20 m band, the current claim that the effect is "tail-dominant and bulk-negligible" and that mean-based analyses are unaffected may not hold.

### V9 — GRSL letter numerical integrity
- **Status:** In progress. Two defects corrected 2026-10-29, one open.
- **Corrected:** decay exponent 0.054 → 0.107 in abstract and Section III-A (pending recomputation from truth4); the "four to five times LoD95" claim replaced with measured values (0.130 m unscreened, 0.691 m fully screened).
- **Open defect:** the letter states 0.691 m as the "median undisturbed forest cell" increment. That figure is from the U2 population, which is not restricted to forest map groups. On the letter's own main population (G3 forest_loss_off, 125,888 cells) the figure is **0.467 m, about 2.0x LoD95**. Must be fixed before submission: either quote 0.467 m / 2.0x, or state explicitly which population 0.691 m describes.
- **Evidence:** `reports/review_grsl_draft_2026-10-29.md`; `reports/independent_check_g3_and_vegmap_2026-10-29.md` section 3; backup `paper/grsl_main.tex.bak-2026-10-29`.

### V11 — Canopy-stratified detection floor
- **Status:** **Measured 2026-10-29 on a validated pipeline.** Awaiting independent review.
- 41% of the 25,569 cells behind the published floor are under 1 m tall, where LoD95 is 0.067 m. In canopy the floor is 2.2-2.3x the pooled value: LoD95 0.508 m at 5-10 m and 0.540 m at 10-20 m, against a published pooled 0.235 m.
- **Consequences:** U2's T_min rises from 3.06 yr to 6.6-7.0 yr at the recorded 0.077 m/yr median growth. The letter's 0.467 m `forest_loss_off` increment falls from 1.98x the floor to 0.86-0.92x — at or below the detection limit.
- **Second signal:** mean difference is -0.006 m on bare cells but -0.198 m at 5-10 m, over a one-year interval. Candidate cause is the epoch scan-angle difference (median 7 degrees, >10 degrees on 26.6% of tiles). Not yet tested on the 2013-2022 pair, which is where growth is actually measured.
- **Evidence:** `reports/a1_truth4_recovery_2026-10-29.md` Finding 2; `scripts/a1_stratified_floor.py`.
- **Caveat:** measured on the 2022-2023 pair. Carrying it to 2013-2022 is an assumption B2 must test.

### V12 — Bias removal: config contradicts code
- **Status:** Documentation defect, confirmed by code inspection 2026-10-29.
- `configs/lidar.yaml` states the pair bias "is removed ... with `lidar.difference.remove_bias`". `remove_bias` has no caller outside its tests, and `change.py:288` deliberately does not remove it, because the bias belongs to the noise-floor pair and each pair carries its own `bare_floor` check.
- The code's behaviour is correct. The config note is wrong and would mislead a reimplementer. **Fix the note.**
- **Correction on record:** an earlier Claude note in this session claimed the bias was unaccounted for. That was wrong.

### V13 — GRSL letter is not under version control
- **Status:** **Blocker.** Found 2026-10-29.
- `paper/` holds only `README.md` and `main.tex` (the earlier map-class-prior paper). No `grsl_main.tex` or its 2026-10-29 backup exists in the repository; last commit touching `paper/` is `f8d7101`.
- The submission-gating artifact lives on one machine, and the Finding 1 benchmark question cannot be checked by anyone else until it is committed.

### V10 — Independent numerical rerun of the GRSL letter
- **Status:** **Not started. Blocked, and blocked on ownership as well as on data.**
- This is **S1**, the submission gate. See `reports/task_spec_s1_independent_rerun_2026-10-29.md`.
- **Data blocker: partly lifted 2026-10-29.** A1's four files are recovered and the exponent is resolved (V1). A rerun can now produce the exponent. The `configs/lidar.yaml` 0.158 figure and B2's fitted error model are still outstanding.
- **Ownership blocker:** the rerun must be executed by a party that did not author the analysis or the letter's text. Claude has done both and is therefore disqualified from running it.

---

## Open defects that must clear before submission

| # | Defect | Owner | Blocks |
| --- | --- | --- | --- |
| D1 | ~~truth4 raw outputs absent~~ **Recovered 2026-10-29.** Decay exponent resolved: 0.054 and 0.107 are one fit in two parameterizations. 0.158 still untested. | Satvik / Lakshay | B2 only |
| D6 | **GRSL letter may now state 0.107 against the 0.5 benchmark**, mixing scale space and cell-count space. Wrong by a factor of two if so. Unverifiable until D8 clears. | Whoever holds the letter | GRSL submission |
| D7 | **LoD95 is pooled across canopy strata and 41% of its cells are bare ground.** In canopy the floor is 2.2x larger. U2's T_min and the letter's "2.0x LoD95" both rest on the pooled figure. | Lakshay | U2, detectability claims in the letter |
| D8 | **`paper/grsl_main.tex` is not in the repository.** One-machine risk, and it blocks D6. | Lakshay | D6, GRSL submission |
| D9 | Unexplained -0.2 m one-year canopy offset on stable cells, absent on bare ground. Candidate cause: epoch scan-angle difference. Untested on the 2013-2022 pair. | — | B2, growth measurement |
| D10 | `configs/lidar.yaml` describes a bias-removal step the code deliberately does not perform. | — | Reproducibility |
| D2 | 0.691 m labelled as "undisturbed forest" but drawn from the U2 population | — | GRSL submission |
| D3 | W3 has no independent human sign-off | Rehaan | Any wire claim in the paper |
| D4 | No analysis data outside one laptop | Lakshay | Reproducibility, Zenodo release |
| D5 | Distribution lines untested; "bulk-negligible" claim unverified against them | Satvik | F4 wording in PAPER_CONTENTS |
