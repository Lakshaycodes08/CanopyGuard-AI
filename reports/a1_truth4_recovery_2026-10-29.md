# A1: truth4 raw outputs recovered, and a canopy-stratified noise floor

Run 2026-10-29. Files supplied by Satvik; analysis by Claude in session
`01Szq9tahJkkowhZniybp9ta`. **Status: independently recomputed from the raw
rasters using this repository's own rules. The published 10 m noise floor
reproduces exactly.** Script: `scripts/a1_stratified_floor.py`.

## Provenance

| File | SHA-256 |
| --- | --- |
| `noise_floor.json` | `84a82b3cb62463224f6535e0cba55efc85240416153763df8b523f8fd144b9d8` |
| `build_log.json` | `9fef191c2285ee90bfb7e88a403805b4c7eef83ad55c475cc38fc0aea1949fda` |
| `plan.json` | `3948aca2b7bbc6bbaed3d9cf2e2379e797fce6633a82b98a868bd3bfce907f70` |
| `footprints.json` | `f3a022e1f68c26cb85684752e8223484f95905250495a787d00550fbf8e82e51` |
| per-tile CHM archive (104 GeoTIFFs, 52 tiles x 2 epochs) | `4065790e44e93ddeeddf4d964757a098a95afb957234d7262c362791c8d3b694` |

The 52 tile ids in the archive match the 52 admitted tiles in
`noise_floor.json` exactly. **A1 is cleared.** These belong under DVC in
`data/processed/truth4/`, not in Git.

## Pipeline validation

Reimplemented from `configs/lidar.yaml` and `src/canopyguard/lidar/`:
stable-cell limit 3.0 m at 1 m, both epochs masked before aggregation,
aggregation to 10 m by mean with `min_valid_fraction` 0.5, sigma as NMAD
(1.4826 x MAD).

| | Cells | sigma | mean | LoD95 |
| --- | ---: | ---: | ---: | ---: |
| Published | 25,569 | 0.120079 | −0.07996 | 0.235354 |
| Recomputed here | 25,569 | 0.120079 | −0.07996 | 0.235354 |

Exact to six decimals on every quantity. The implementation is correct and the
stratified results below rest on a validated pipeline.

---

## Finding 1 — 0.054 and 0.107 are the same number. D1 is closed.

`src/canopyguard/evaluation/detectability.py` defines the model explicitly:

> The model is sigma = a * N ** -b. Spatially independent error gives b = 0.5.

with `N = (scale / base_scale) ** 2`, and `lod95_at` converts to linear scale
using `(scale / 100.0) ** (-2.0 * exponent)` — the factor of two, in the code.

Refitting the four admitted scales confirms it:

| Fit | Exponent | r² | Coefficient |
| --- | ---: | ---: | ---: |
| sigma against linear scale | 0.107996799 | 0.861961423 | 0.150813708 |
| sigma against cell count N | **0.053998399** | 0.861961423 | 0.150813708 |
| Stored in `noise_floor.json` | 0.053998399 | 0.861961423 | 0.150813708 |

0.054 is the exponent in cell-count space; 0.108 is the same decay in linear
scale space. `reports/research_design.md` line 141 already states the correct
pairing: "exponent 0.054 against 0.5 for spatially independent error". The
matching benchmark in scale space is 1.0, not 0.5. Either way the error decays
at **10.8%** of the independent rate.

**The 0.158 figure cited in `ACTION_PLAN.md` is not reproducible.** Fitting the
`configs/lidar.yaml` sigma values gives 0.1069 in scale space and 0.0535 in N
space; adding the 100 m reference gives 0.1062 / 0.0531; the LoD95 column gives
0.1081. Nothing yields 0.158. There is no third value and no conflict. The
`ACTION_PLAN.md` note that 0.054 "appears to have come from the
independent-error comparison rather than from the fit" is also wrong — it came
from the fit.

**Consequence for the letter.** The 2026-10-29 change from 0.054 to 0.107 was
not a correction. If the letter still compares against 0.5, it now pairs a
scale-space exponent with a cell-count-space benchmark and is wrong by a factor
of two. **I could not check this: `paper/grsl_main.tex` is not in the
repository** — see Finding 4.

---

## Finding 2 — the published detection floor is measured mostly on bare ground

This is the substantive result, and it was invisible until the rasters arrived.

Splitting the same 25,569 stable 10 m cells by the 2022 canopy height of each
cell:

| 2022 height (m) | Cells | sigma | LoD95 | mean | vs pooled |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0–1 | 10,492 | 0.0344 | 0.0674 | −0.006 | 0.29x |
| 1–2 | 3,334 | 0.1405 | 0.2754 | −0.043 | 1.17x |
| 2–5 | 3,522 | 0.2096 | 0.4108 | −0.123 | 1.75x |
| 5–10 | 4,103 | 0.2594 | 0.5084 | −0.198 | 2.16x |
| 10–20 | 3,314 | 0.2755 | 0.5400 | −0.172 | 2.29x |
| 20–30 | 665 | 0.2242 | 0.4395 | −0.036 | 1.87x |
| >30 | 139 | 0.2261 | 0.4432 | −0.021 | 1.88x |
| **Pooled (published)** | **25,569** | **0.1201** | **0.2354** | **−0.080** | — |

**41% of the cells behind the published floor are under 1 m tall**, and on
those the error is almost nil (LoD95 0.067 m). They dominate the pooled median
and pull it down. In actual canopy the floor is **2.2 to 2.3 times larger**
than the number the project uses everywhere.

This is not an implementation bug — the code is correct and reproduces exactly.
It is that a single pooled floor is applied to a population it does not
describe.

### What moves

**U2 detectability** (`reports/u2_detectability_rule_2013-2022.md`), at the
recorded median growth of 0.077 m/yr:

| Floor used | LoD95 | T_min |
| --- | ---: | ---: |
| Published pooled | 0.235 m | 3.06 yr |
| 5–10 m canopy | 0.508 m | 6.60 yr |
| 10–20 m canopy | 0.540 m | 7.01 yr |

T_min roughly doubles. The claim that 73.4% of undisturbed cells exceed LoD95
over 8.96 years is computed against the pooled floor and will fall
substantially against a canopy-appropriate one.

**The GRSL letter's increments**, as multiples of the floor:

| Increment | vs pooled | vs 5–10 m | vs 10–20 m |
| --- | ---: | ---: | ---: |
| 0.130 m unscreened | 0.55x | 0.26x | 0.24x |
| 0.467 m `forest_loss_off` | 1.98x | 0.92x | 0.86x |
| 0.691 m U2 screened | 2.94x | 1.36x | 1.28x |

On a canopy-appropriate floor, **the median nine-year increment on the letter's
own main population sits at or just below the detection limit.** The "about 2.0
times LoD95" framing does not survive.

This does not break the letter's thesis. It is the same thesis: the apparent
margin above the floor comes from how the population and the floor were each
selected, not from the signal. But several specific numbers and the framing
around them need reworking before submission.

### A second signal in that table

The mean is −0.006 m on bare cells but −0.198 m at 5–10 m and −0.172 m at
10–20 m. Over a one-year interval where growth should be about +0.077 m,
canopy reads roughly 0.2 m **lower** in 2023 than 2022 on cells classed as
stable. The pooled −0.080 m hides this entirely.

The build log offers a candidate cause: mean scan angle differs between epochs
by a median of 7°, and by more than 10° on 26.6% of tiles. Off-nadir geometry
suppresses apparent canopy top height, and it would not affect bare ground.

**This needs following up before B2**, because the 2013–2022 pair is where the
study actually measures growth, and nothing has established that it is free of
a comparable canopy-dependent offset.

---

## Finding 3 — the config's bias note contradicts the code

I previously wrote that the −0.08 m bias was "unaccounted for". **That was
wrong and I am correcting it.** `configs/lidar.yaml` records `bias_m: -0.08`,
and `change.py` has `bare_floor`, which measures each pair's own bias on cells
bare in both epochs. The design is sound.

The defect is narrower and is a documentation one. `configs/lidar.yaml` says
the bias "is removed from pair differences with `lidar.difference.remove_bias`
before comparison against the limit of detection". But `remove_bias` has no
caller anywhere outside its own tests, and `change.py:288` states the opposite
on purpose:

> The noise-floor pair bias is not removed here. It belongs to that pair,
> and this pair carries its own check on bare ground.

The code's position is the defensible one. The config describes a pipeline that
does not exist, and anyone reimplementing from it would build something
different. **Fix the note, not the code.**

---

## Finding 4 — the GRSL letter is not under version control

`paper/` contains only `README.md` and `main.tex`, and `main.tex` is the
earlier paper, "A Spatially Blocked Test of a Map-Class Canopy-Height Growth
Prior in Northern Sonoma County". The last commit touching `paper/` is
`f8d7101` (PR #20).

There is no `grsl_main.tex` and no `grsl_main.tex.bak-2026-10-29` anywhere in
the repository. The letter written 2026-10-25 and edited 2026-10-29 exists only
on one machine.

Two consequences. The benchmark question in Finding 1 **cannot be checked by
anyone but whoever holds that file**. And the artifact the whole submission
gates on carries the same single-laptop risk as D4. It should be committed
before anything else in this report is acted on.

---

## Finding 5 — admission is non-random, and two gate checks are loosely worded

52 of 284 tiles admitted (18.3%): 152 rejected for coverage below the minimum,
80 because the epoch coverages disagreed. Admission turns on coverage
agreement, which tracks flight-line geometry, so the admitted set is plausibly
the best-behaved fifth. Direction of bias is toward an optimistic floor.

- `reference_sigma_m` is 0.0917 m with `reference_source: "extrapolated"`. The
  `reference_sigma_available` check passed on an extrapolated value. The repo
  is honest about this in `research_design.md`; the letter should be too.
- `sigma_falls_with_scale` passed, but sigma is not monotonic: it falls
  10→20 m and 20→30 m, then rises slightly 30→50 m (+0.0004, inside the 2.2%
  relative error at 50 m). A wording issue, not a result issue.

---

## What this does not establish

- The G1 pipeline was not rerun from point clouds. This recomputes the floor
  from the delivered per-tile CHMs.
- The stratified floors are measured on the **2022–2023** pair. Applying them
  to 2013–2022 assumes the error structure carries over. That assumption is
  now the thing most worth testing, and it is what B2 should cover.
- Height bands use the 2022 mean cell height as the stratifier. A p95-based
  stratifier would be closer to how the labels are built and may shift the
  bands.
- Nothing here touches label construction, the vegetation join, the wire flags
  or the terrain join.
