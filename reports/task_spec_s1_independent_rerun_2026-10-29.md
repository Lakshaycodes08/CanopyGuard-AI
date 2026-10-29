# Task spec — S1: independent numerical rerun of the GRSL letter

Written 2026-10-29. Owner: **unassigned — see section 1.**
Branch: `s1/grsl-independent-rerun`.

This is the gate on GRSL submission. Every number in `paper/grsl_main.tex`,
recomputed from the data by a party that did not produce the analysis.

---

## 1. Who may run this — read before assigning

The value of S1 is independence. Nothing else. If independence is lost, the
task produces agreement without producing evidence, which is worse than not
running it, because it creates a signed record that the numbers were checked.

**Claude is disqualified from executing S1.** Two reasons, both on record:

1. Claude corrected two numbers in `paper/grsl_main.tex` on 2026-10-29 — the
   decay exponent (0.054 → 0.107) and the "four to five times LoD95" claim.
2. `reports/independent_check_g3_and_vegmap_2026-10-29.md` section 3 states
   plainly: *"I introduced this when I rewrote that sentence."* Claude is an
   author of the letter's analysis text.

The project's own rule already encodes this. `ACTION_PLAN.md` B5 specifies the
reviewer must be **"not the author of either."** The same standard applies here.

**A fresh AI agent is also not sufficient on its own.** An agent spawned for
this task inherits the framing of whoever briefs it — which numbers to check,
which populations are the right ones, what "matching" means. That yields
*independent re-execution*, not *independent replication*. It is worth doing as
a first pass, but it must be labelled as re-execution in `VALIDATION_LOG.md`
and it does not clear the gate on its own.

**Recommended owner:** whichever of Satvik or Rehaan has not worked on the
GRSL letter. Note that B4 is already Satvik's and B5 is already Rehaan's, so
this is a real scheduling decision, not an automatic one.

## 2. Hard blocker

The headline decay exponent cannot be finalised until **A1** clears — the four
truth4 JSON files reaching `data/processed/truth4/`. Three values are on record
(0.054, 0.107, 0.158) and none is settled. S1 can begin on everything else, but
it cannot be signed off while that number is open.

Do not let a rerun "confirm" 0.107. It is itself a provisional fit made during
review, not a measured value.

## 3. Method — the constraint that makes it independent

**Compute first, compare second.** The reviewer must not read the existing
result JSONs, `reports/growth_curve_check_2013-2022.md`, or
`scripts/independent_g3_check.py` before producing their own numbers. Work from
the data and the written protocol in `configs/forecasting.yaml`, then open the
published values and diff.

If the published numbers are read first, the exercise becomes confirmation.
This is the single most important instruction in this spec.

Work from a clean checkout and `dvc pull` — which requires **A2** to have been
done. If the data still exists only on one laptop, S1 cannot be independent in
any meaningful sense, because the reviewer is reading the author's working copy.

## 4. What to recompute

Every number that appears in `paper/grsl_main.tex`:

- The G3 stage-one comparison: cell counts (125,888 / 76,980), no-change MAE,
  median-prior MAE, paired differences and whole-block bootstrap intervals at
  1 km, 2 km and 5 km.
- The Table I NMAD column and the decay exponent fitted to it.
- The median canopy-cell increments: 0.130 m unscreened, 0.691 m screened, and
  **0.467 m on the forest_loss_off population** — see the open defect below.
- LoD95 at 10 m and the multiples quoted against it.
- The screening-inflation contrast that is the letter's thesis.

## 5. Open defect this rerun must resolve

The letter states 0.691 m as "the median undisturbed forest cell" increment.
That figure comes from the U2 population, which is **not restricted to the
forest map groups** and is not the population any other number in the letter
uses. On the letter's own main population the figure is 0.467 m, about 2.0x
LoD95, not 2.9x.

The reviewer should compute the increment on all three populations
(forest_loss_off, forest_loss_on, U2) independently and state which the letter
should quote. The argument survives either way — the unscreened 0.130 m is
below the floor on every population — but the published sentence is currently
wrong as labelled.

## 6. Acceptance criteria

A signed note at `reports/s1_independent_rerun_grsl.md` containing:

1. Who ran it, on what date, from which git revision and which `dvc` data hash.
2. An explicit statement that the published values were not consulted before
   computing, or an honest statement of where they were.
3. A row-by-row table: published value, recomputed value, difference.
4. Every discrepancy investigated to a cause, not merely noted.
5. A statement of which numbers remain unresolved pending A1.
6. A recommendation: submit, or do not submit.

A rerun that reports "all numbers match" without section 2 of its own method
being satisfiable is not a pass. Record it in `VALIDATION_LOG.md` V10 at the
status it actually earned.
