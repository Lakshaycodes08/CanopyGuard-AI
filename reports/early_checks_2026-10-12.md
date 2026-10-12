# Early checks for the LiDAR-change study

Prepared: 2026-10-12. These are research gates, not passed results.

## Project description for the shared workspace

CanopyGuard-AI asks whether multi-year canopy-height change in northern Sonoma
can be predicted and validated against repeat airborne LiDAR, and whether the
resulting evidence can improve transmission-corridor prioritization. The first
baseline is a vegetation-alliance growth curve fitted from 2013 canopy height
and evaluated against 2022 height change on independently screened,
undisturbed cells. ECHOSAT is a candidate temporal height product to check for
2018-2023 coverage. GEDI is an independent cross-check, not a one-year growth
target. A risk ranking is research prioritization, not a clearance or safety
certification; conductor geometry is not yet available.

## Assignments

| Owner | Check | Time | Pass evidence |
| --- | --- | --- | --- |
| Satvik | Inspect 2013-2022 LiDAR labels near lines and towers for wire or tower returns misclassified as canopy. | 1-2 days | No excess of isolated tall returns close to power lines, using matched off-corridor or buffered controls. Save the sampling rule, plots, counts, and suspect-cell IDs. |
| Rehaan | Test ECHOSAT download and 2018-2023 overlap with the configured Sonoma box. | Half a day | Downloadable maps have real, non-nodata values over the exact study geometry and requested years. Save source version, URLs or query, per-year valid-area counts, and a small visual sample. |
| Codex | Fit a 2013-height growth curve per Sonoma vegetation alliance and compare with zero change. | 2-3 days | On independently screened undisturbed cells, a held-out spatial-block evaluation improves mean absolute error over zero change. Report each alliance's sample size, curve, uncertainty, and any groups that fail. |

## Growth-check gate

Use the deduplicated 2013-2022 label archive from `configs/lidar.yaml`.
Exclude `overlap_disputed` cells until their spatial review is complete. Join
the official 2013 Sonoma Veg Map alliance polygons to cell centers. Treat
mixed classes and boundary cells as uncertain rather than forcing a species.
Define undisturbed cells from positive persistent-forest evidence and the
CAL FIRE, MTBS, and Landsat trajectory screens in
`reports/phase1_data_protocol.md`. Do not infer stability solely from a
small LiDAR change or absence from one fire database. Fit on 2013 height only,
with no 2022 features. Compare held-out 2022 change against the zero-change
prediction and resample by spatial block. The fitted curve is the ecological
prior baseline in the paper only if this gate passes.

The local label archive has 1,478,103 unique valid cells but no alliance or
independent disturbance-screen fields. Excluding 198 disputed cells leaves
1,477,905 cells. A preliminary zero-change mean absolute error is 1.212 m
over those cells and 2.078 m over 718,162 cells with 2013 mean canopy height
at least 2 m. These are descriptive values, not undisturbed-set scores or
evidence that a growth curve passes. The official Sonoma service reported
29,346 polygons intersecting the configured study box on 2026-10-12.

## Literature guard

Bahreini and Hammad's 2025 review (doi:10.3390/f16111658) includes an earlier
LiDAR plus Richards-growth encroachment study and proposes species-aware growth
models and maintenance prioritization. Do not claim that fitting growth curves
or connecting growth to corridor risk is new. The testable contribution is the
quality-controlled open evidence and independent comparison with strong
baselines. See `reports/literature_review.md` and `reports/claims_log.md`.

## Shared project context

Claude's project help says the project name and description are not available to
Claude in project chats. To make the LiDAR-change goal available to teammate
agents, place the project-description paragraph above in both the visible
project description and the Project instructions or knowledge. Source:
https://support.claude.com/en/articles/9519177-how-can-i-create-and-manage-projects

GitHub handoffs: Satvik https://github.com/Lakshaycodes08/CanopyGuard-AI/issues/6;
Rehaan https://github.com/Lakshaycodes08/CanopyGuard-AI/issues/7;
Codex growth check https://github.com/Lakshaycodes08/CanopyGuard-AI/issues/8.
