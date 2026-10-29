# Task spec — B4 / W4: distribution-line enrichment

Written 2026-10-29. Owner: **Satvik**. Branch: `b4/distribution-lines`.
Supersedes nothing. Companion to `reports/w3_tall_tail_enrichment_2013-2022.md`.

---

## 1. Why this is not a cheap cleanup

`ACTION_PLAN.md` calls this "a named limitation and cheap to close". On
inspection it is more than that, for one physical reason.

Transmission conductors on the 41 CEC features hang from towers roughly 30-60 m
up. That is **above** almost all real canopy, which is why the contamination
shows as a tall tail and why W3 could call it "tail-dominant and
bulk-negligible".

Distribution conductors sit on poles at roughly **10-15 m**. That is **inside**
the bulk of the height distribution. W3 reports 440,500 cells with 2013 p95
between 10 and 20 m — a third of the archive.

Two consequences follow, and both are testable:

**(a) The "bulk-negligible" claim is currently unverified, not established.**
W3 showed transmission lines do not measurably bias mean-based results. It did
not and could not show that for distribution lines, because they were never in
the distance computation. If distribution conductors contaminate the 10-20 m
band, then `PAPER_CONTENTS.md` F4's statement that "mean-based analyses are
effectively unaffected" is a claim the project has not earned, and the
downstream damage result (B3) could move.

**(b) The existing controls may be contaminated.** W3 draws controls beyond
250 m from a *transmission* line. Distribution lines follow roads and are far
denser. A meaningful share of current "control" cells probably sit near a
distribution conductor. If so, the published transmission enrichment ratios are
**biased downward** — the true contrast is larger than reported.

Note (b) cuts in the opposite direction from the naive expectation. Adding
distribution lines will raise the near-line base rate, which mechanically
*lowers* enrichment ratios; but cleaning the controls *raises* them. Report
both effects separately or the result will be uninterpretable.

---

## 2. Blocker to resolve first — do this before writing any analysis code

`MEMORY.md` records "92 power lines, 1957 spans resolved from OSM" during the
corridor-driven label build on Colab, 2026-09-24. **It is not established that
this geometry was ever persisted as a layer in the checkout.** `dvc.lock` and
the W3 inputs reference only `data/interim/cec/cec_lines_study_box.geojson`.

First action: confirm whether a saved OSM line layer exists. Then one of:

- **If it exists** — record its path and SHA-256 and proceed.
- **If it does not** — it must be re-fetched, and this introduces a
  reproducibility problem that must be handled explicitly, because **OSM is a
  live database**. A query run in November 2026 will not necessarily return the
  same 92 lines a query run in September 2026 returned. Do not quietly re-fetch
  and assume the counts match.

If re-fetching: use a dated Overpass query against a **named Overpass API
snapshot or a dated Geofabrik extract**, archive the raw response in
`data/interim/osm/` under DVC with its hash, record the query string and the
extract date verbatim in the report, and state whether the line and span counts
match 92 / 1,957. If they do not match, report the new counts and say so. A
mismatch is a finding about OSM volatility, not a failure.

---

## 3. What to run

Keep `scripts/w3_tall_tail_enrichment.py` and `scripts/check_wire_labels.py`
unchanged in their logic. Extend only the line layer they consume.

Fix all of the following **before reading any rate**:

- Near band: `dist_to_line_m` <= 30 m, as in W3.
- Threshold ladder: 2013 p95 >= 20, 25, 30, 35, 40, 45 m, unchanged.
- **Add a low ladder for the distribution hypothesis:** 2013 p95 >= 8, 10, 12,
  15, 18, 20 m. This is the band where a 10-15 m conductor would show, and it is
  the whole point of the task. Declare it now, in writing, before any rate.
- Uncertainty: whole-tile bootstrap, 2,000 draws, seed 42, percentile interval.
- Controls: beyond 250 m from **any** line, transmission or distribution,
  stratified by tile and canopy fraction exactly as `check_wire_labels.py` does.

Produce **four** enrichment curves, not one:

| # | Line layer | Control definition | Purpose |
| --- | --- | --- | --- |
| 1 | Transmission only | >250 m from transmission | Reproduces published W3. Must match. |
| 2 | Transmission only | >250 m from **any** line | Isolates control contamination (b) |
| 3 | Distribution only | >250 m from any line | The distribution signal on its own |
| 4 | Both combined | >250 m from any line | The headline combined result |

Curve 1 is a regression check. If it does not reproduce W3's published
numbers, stop and report that before doing anything else.

Run the placebo for curves 3 and 4: lines displaced 400 m in four directions,
real-line cells excluded. W3's transmission placebo gave 0.47-1.03. If the
distribution placebo does not sit near 1.0, the estimator is manufacturing the
effect on the denser layer and the result is not usable.

Also run, on the distribution layer:
- The biologically-impossible-cell test, but at a threshold appropriate to
  distribution height. Grass or shrub with p95 >= 18 m is the analogue of the
  45 m transmission test.
- The mean-to-p95 gap, which is the discriminator that worked for transmission
  (52.2 m p95 against 9.4 m cell mean). Expect it to be **much weaker** here: a
  12 m conductor over 3 m shrub is a far less extreme signature than a 52 m
  conductor over the same shrub. If it does not discriminate, say so plainly.
  A negative result here is publishable and is better than a strained one.

---

## 4. Acceptance criteria

The task is complete when `reports/b4_distribution_line_enrichment.md` and
`.json` contain all of:

1. The provenance of the OSM layer: path, SHA-256, query string, extract date,
   and line/span counts against the recorded 92 / 1,957.
2. All four enrichment curves over both ladders, with 95% whole-tile bootstrap
   intervals, cell counts and control counts for every row.
3. Curve 1 compared row by row against the published W3 table, with any
   discrepancy stated.
4. The placebo ratios for curves 3 and 4.
5. A direct, explicit answer to the question: **does the contamination extend
   into the 10-20 m bulk?** Yes or no, with the numbers that settle it.
6. A statement of whether `PAPER_CONTENTS.md` F4's "bulk-negligible" and
   "mean-based analyses are effectively unaffected" wording survives. If it does
   not, propose the replacement wording.
7. Git revision, config hashes, and the seed, as E8's preregistration requires.
8. The limitations section: OSM distribution lines are volunteer-mapped and
   incomplete, so absence of a mapped line is not evidence of absence of a
   conductor. This asymmetry must be stated — it means any null result is weak
   and any positive result is a lower bound.

## 5. What must not be claimed

- No clearance, encroachment or safety inference. No conductor geometry exists.
- Not every flagged cell contains a wire.
- Do not select a threshold, ladder point or vegetation subgroup after seeing a
  rate. If you do, label it post hoc, as the existing reports do.
