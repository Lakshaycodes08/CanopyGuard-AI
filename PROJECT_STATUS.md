# CanopyGuard-AI project status

Checked: 2026-10-15. The current work is on `codex/stage2-terrain-paper`.
GitHub and research status can change after this snapshot; verify linked issues
and pull requests before relying on a closure claim.

## Decision

Phase 0 is **GO** on the exact northern Sonoma feasibility box, supported by
`reports/data_feasibility.md`. Phase 1 is **CONDITIONAL GO**, not complete:
the 2013-2022 label and growth-prior work has advanced, but the full
prospective feature, validation, and operational risk chain remains unproved.
The status in `reports/phase1_data_protocol.md` is the formal Phase 1 gate.

## Verified and open work

| Item | State | Evidence and limit |
| --- | --- | --- |
| Phase 0 six-gate feasibility | Completed and verified | `reports/data_feasibility.md` records GO for the exact study box. This is feasibility, not forecast validation. |
| PRs [#5](https://github.com/Lakshaycodes08/CanopyGuard-AI/pull/5), [#9](https://github.com/Lakshaycodes08/CanopyGuard-AI/pull/9), [#11](https://github.com/Lakshaycodes08/CanopyGuard-AI/pull/11), [#12](https://github.com/Lakshaycodes08/CanopyGuard-AI/pull/12), [#13](https://github.com/Lakshaycodes08/CanopyGuard-AI/pull/13) | Completed and merged | GitHub merge state checked. PR #13's wire exclusion is implemented; its preset review criterion failed and independent scientific assessment remains open. |
| PR [#16](https://github.com/Lakshaycodes08/CanopyGuard-AI/pull/16) | Implemented but awaiting required review | Open at `a66cfbb`; CI succeeded, but GitHub reports `REVIEW_REQUIRED`. A standard merge attempt was rejected by branch policy. No human scientific sign-off is recorded. |
| Issue [#8](https://github.com/Lakshaycodes08/CanopyGuard-AI/issues/8) | Implemented but awaiting merge and review | G3 implementation and report are in PR #16. Issue #8 stays open until the protected-branch merge can complete. |
| Issue [#19](https://github.com/Lakshaycodes08/CanopyGuard-AI/issues/19) | In progress | Assigned to @thesat7vik for the post hoc A rule, negative-result framing, and LiDAR-loss-on billing. `human_review` remains `pending`. |
| Issues [#14](https://github.com/Lakshaycodes08/CanopyGuard-AI/issues/14) and [#15](https://github.com/Lakshaycodes08/CanopyGuard-AI/issues/15) | Planned, deferred | Point-level thin-return filter and 2018-2023 wildfire co-coverage check. Both remain open. |
| G1, 2022-2023 LiDAR noise floor | Completed and verified | `MEMORY.md` records a pass on 284 seam tiles: shift 0.137 m, 10 m LoD95 0.235 m. The 0.054 spatial decay exponent qualifies interpretation as an offset field, not independent error. |
| G2 | Blocked: outcome not located | No G2 gate record or result was found in the checked repository reports and memory. Do not infer a pass from G1 or G3. Locate the gate definition and run record before changing this state. |
| G3, stage-one growth prior | Implemented but awaiting scientific review | `reports/growth_curve_check_2013-2022.md` reports the spatial median-prior gate PASS on both forest screens. The Chapman-Richards curve does not beat the median. The empirical A rule and screen interpretation were post hoc; issue #19 holds the review. |
| 2012 3DEP terrain on 10 m labels | Completed and verified locally | `data/interim/terrain_10m.parquet` has one complete row per 1,478,103 existing `cell_id` values. DVC and provenance sidecars record the source and hashes. The label CRS is EPSG:6339. The former 100 m config value was unused and corrected. |
| E4 ridge and E5 LightGBM stage-two gate | Completed and verified locally; gate rejected | `reports/stage2_residual_check_2013-2022.md` reports both FAIL on the frozen forest loss-OFF 2 km gate. Stage-one MAE is 1.256 m; ridge 1.336 m and LightGBM 1.309 m. The positive loss-ON sensitivity does not change the decision. |
| Manuscript | Implemented but awaiting validation | `paper/main.tex` drafts G3 and stage-two results with limitations. Human scientific review and publication checks are pending. |
| Sentinel-2, GEDI, ECHOSAT | Planned for their documented roles | Sentinel-2 observations after 2013 cannot predict the 2013-to-2022 outcome. GEDI is an independent height cross-check; ECHOSAT is a product benchmark. Neither is a stage-two predictor. |
| E6/E7/E9/E10 and span ranking | Rejected/superseded for this deadline | These ladder entries and operational span ranking are descoped from the current 31 October package. The old config ladder lists them as legacy plans; no implementation or validated result is claimed. |

## Research boundary

The present height-change result is a spatially blocked comparison on screened
LiDAR cells. It is not a validated future-year forecast, utility clearance
measurement, or safety certification. Approximate public power-line geometry
cannot supply conductor clearance. Persistent-forest screening, model
generalization, and a validated independent risk check need further evidence.

## Next action

Obtain the required PR #16 review and the scientific answers in issue #19.
After PR #16 can merge under branch policy, close issue #8 as implemented with
scientific review pending and bring this status file through its feature PR.
