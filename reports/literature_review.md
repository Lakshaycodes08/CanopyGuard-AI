# Phase 1 literature review

Reviewed: 2026-09-15

## Status

This is the verified core comparison set for Phase 1. It is not yet a systematic
review and does not prove an absolute novelty claim. The immediate purpose is
to prevent the project from claiming novelty for ideas that are already
published and to turn the review into concrete experiment requirements.

The review uses publisher pages, DOI records, accepted manuscripts, and paper
text. The Firecrawl paper index was unavailable during this pass, so discovery
used primary-source web research instead.

## Review question

What has already been demonstrated for remote sensing of vegetation near power
lines, canopy-height mapping through Sentinel-2 and GEDI, vegetation growth
forecasting, and maintenance scheduling, and what defensible research gap is
left for CanopyGuard-AI?

## Comparison table

| Study | Objective and data | Method | Reported evaluation | Strength | Main limitation for our question | Tough reviewer question |
| --- | --- | --- | --- | --- | --- | --- |
| [Mongus et al. (2021)](https://doi.org/10.3390/rs13245159) | Predict vegetation growth and detect encroachment in transmission corridors using repeat airborne LiDAR and contextual maps. | Context-specific weak regression models plus a rasterized funnel-shaped clearance filter. | Growth RMSE about 1 m; encroachment detection error 0.37 m on the reported test data. | Directly joins growth prediction and corridor geometry. | Depends on repeat airborne LiDAR and reports experimental validation on limited test systems; no crew scheduling benchmark. | Does the method generalize to a new region, ecology, and sensor without new LiDAR flights? |
| [Chen et al. (2022)](https://doi.org/10.1016/j.jag.2022.102740) | Predict future tree encroachment from UAV LiDAR, individual-tree heights, species labels, and plot growth records. | Richards growth curves for Masson pine and Eucalyptus plus two-stage bounding-box intersection tests. | Growth-model R2 values about 0.81 to 0.86 and RMSE about 2.3 to 2.6 m; detection was about 76 times faster than point traversal. | Makes species-specific growth knowledge operational and identifies individual future encroaching trees. | One roughly 500 m test segment, two species, expensive UAV LiDAR, and field verification still required. | How accurate is transfer to mixed forests with uncertain species and moving conductors? |
| [Yung et al. (2024)](https://doi.org/10.1109/IGARSS53475.2024.10641974) | Assess individual-tree risk along power lines using high-resolution satellite imagery and drone-LiDAR truth. | Random Forest height map, treetop detection, crown delineation, failure-zone geometry, and four-level risk classification. | Hitachi reports precision 0.922, recall 0.819, F1 0.868, and MAMAE 0.669. | Shows that satellite-derived tree risk can approach a LiDAR-based reference. | The accessible summary does not establish a multiyear growth forecast, open benchmark, or trimming optimizer. | Are results reproducible outside the proprietary imagery, labels, and operating context? |
| [Lang et al. (2023)](https://doi.org/10.1038/s41559-023-02206-6) | Produce a global 10 m canopy-height map from Sentinel-2 and sparse GEDI labels. | Probabilistic fully convolutional ensemble with sparse supervision and predictive uncertainty. | Held-out GEDI RMSE 6.0 m and bias 1.3 m; independent LiDAR average RMSE 7.9 m within GEDI coverage. | Global scale, explicit uncertainty, spatial holdout, and independent airborne-LiDAR evaluation. | The model targets a 2020 map and is not designed for strong seasonality outside its selected acquisition period. | Can errors at 10 m support corridor prioritization when clearance decisions occur at finer scales? |
| [Pauls et al. (2025)](https://arxiv.org/abs/2501.19328) | Map annual canopy height across Europe from 2019 to 2022 using Sentinel time series and GEDI labels. | A 3D U-Net consumes 12 monthly Sentinel-2 images and Sentinel-1 information across years. | Reported MAE 4.76 m for the strongest model and better results than compared height maps; seasonal-input ablations are included. | Direct evidence that monthly temporal information improves multiyear canopy-height mapping. | The authors state that minor natural growth remains difficult to observe over four years because uncertainty is large relative to slow growth. | Does the model measure biological growth, or mainly disturbance and interannual sensor variation? |
| [Jumbo and Moghaddass (2022)](https://doi.org/10.1016/j.apenergy.2022.119234) | Detect vegetation risk from high-resolution aerial imagery and allocate crews in a distribution network. | DCNN segmentation and outage-risk ranking feed vehicle-routing and crew-allocation models. | Experiments use the Bay Area Synthetic Network; the abstract reports high segmentation and risk-prediction accuracy. | Already connects image-derived risk to resource allocation and routes. | Uses high-resolution aerial imagery and a synthetic network; the accessible record does not provide an open, future-height validation benchmark. | Why is a new integrated pipeline needed rather than a lower-cost reproduction of this one? |
| [Jaramillo-Leon and Leite (2022)](https://doi.org/10.1007/s40313-020-00606-8) | Schedule preventive trimming across distribution feeders under competing interruption and maintenance costs. | NSGA-II minimizes customer interruption cost and vegetation maintenance cost under crew, reliability, and priority-zone constraints. | Demonstrated on a real system with 11 feeders and two vegetation-information cases. | Provides a strong scheduling formulation and realistic utility constraints. | Vegetation risk is an optimizer input rather than a remotely sensed, independently validated forecast. | Does forecast-derived risk improve the schedule over current-height or reliability-only inputs? |
| [Canopy height mapping in complex temperate forests (2026)](https://doi.org/10.1016/j.atech.2026.102249) | Map canopy height in structurally complex temperate forest using GEDI, seasonal Sentinel-2, and 2,543 inventory plots. | Random Forest models compare seasonal and multitemporal predictors, GEDI filtering, local calibration, and plot-location correction. | Local multitemporal model RMSE 5.3 m and R2 0.45 against field data; GEDI filtering reduced RMSE from 11.7 m to 8.09 m. | Shows that quality filtering, seasonality, local calibration, and spatial alignment materially affect accuracy. | Optical saturation underestimates tall canopy; sparse GEDI and residual alignment error remain. Data are not publicly shareable. | Will a Sonoma model remain valid across fire history, terrain, and canopy structure without spatial leakage? |
| [Savva et al. (2025)](https://doi.org/10.1109/MGRS.2025.3558741) | Review remote sensing and AI for vegetation hazards in power-line corridors. | Structured review of 2D imagery, LiDAR, AI methods, metrics, and datasets. | Review paper; no new predictive benchmark. | Establishes the current method landscape and identifies fragmented methods and scarce public 3D datasets. | A review cannot establish that our exact proposed combination is novel. | Has the review missed proprietary or recent integrated systems that already cover our claimed gap? |
| [Wang et al. (2025)](https://doi.org/10.3390/f16040578) | Detect and predict transmission-line tree risks from UAV LiDAR, field inventory, and conductor geometry. | Point-cloud classification, 3D catenary reconstruction, field-informed tree growth, and risk detection. | The paper reports field experiments and comparisons with manual and point-cloud-only approaches. | Recent evidence that growth-aware, future tree-risk prediction is already an active integrated research area. | Requires UAV LiDAR and region-specific field/tree equations; it does not provide the proposed free satellite time series and independent repeat-LiDAR benchmark. | Does the lower-cost satellite design retain enough height accuracy to be useful? |
| [Ayobo et al. (2025)](https://doi.org/10.1109/ACCESS.2025.3623468) | Review digital-twin approaches for power-line monitoring and vegetation risk management. | Survey plus a conceptual digital-twin integration framework. | Review article; no new open empirical benchmark. | Shows that predictive monitoring and integrated vegetation-management architectures are established concepts. | The proposed framework is conceptual and does not test our data roles or validation design. | Is CanopyGuard adding evidence, or merely implementing another integration diagram? |
| [Parent et al. (2026)](https://doi.org/10.1016/j.rsase.2026.101928) | Relate LiDAR forest metrics and operational attributes to storm-related distribution outages. | Explainable GIS risk models using proximity pixels, canopy structure, soils, line attributes, and outage records. | Models differentiated zero, one-to-two, and more-than-two outage groups across a large utility service area. | Strong operational evidence that fine-scale LiDAR forest structure can support prioritization. | The utility data are not shareable; the study does not perform one-year canopy forecasting from open satellite time series. | Can an open proxy evaluation support a meaningful claim without confidential outage labels? |
| [Sokolovsky et al. (2026)](https://arxiv.org/abs/2608.18611) | Model vegetation and lightning probability of failure at utility-asset scale. | Geospatial features, MODIS NDVI, utility records, LightGBM, and explainability in a cloud pipeline. | Reports cross-validated discrimination but explicitly does not test strict forward-time forecasting or geographic transfer. | Demonstrates scalable operational asset-risk modeling and exposes the weakness of geolocation-unaware splits. | A recent preprint using confidential utility data, coarse MODIS vegetation, and non-temporal cross-validation. | Does our chronological and spatially blocked open evaluation change the conclusions? |
| [Ding et al. (2026)](https://slgc.nefu.edu.cn/EN/abstract/abstract2639.shtml) | Integrate UAV image measurement, vegetation risk assessment, and clearance scheduling. | ResNet-50 segmentation, multimodal risk grading, clustering, and vehicle routing. | Reports 86.7 percent vegetation classification accuracy, 65.88 percent IoU, 89.3 percent overall risk accuracy, and a 21 percent maintenance-cost reduction. | Directly occupies the broad measurement-assessment-scheduling integration claim. | Relies on UAV imagery and field data; the accessible record does not establish open data, independent repeat-LiDAR validation, or spatially blocked future evaluation. | What is scientifically new beyond replacing proprietary inputs with open ones? |
| [Wanik et al. (2017)](https://doi.org/10.1016/j.epsr.2017.01.039) | Test whether vegetation management, LiDAR tree proximity, and infrastructure data improve Hurricane Sandy outage prediction. | A LiDAR-derived ProxPix layer and utility attributes feed repeatedly balanced Random Forest models on 0.5 km cells. | Models with added vegetation and infrastructure evidence improved by about 5 to 13 percent, depending on metric and inputs. | Operationally links fine vegetation structure to outage occurrence. | One storm and utility territory, confidential operational data, and no future canopy-height forecast. | Can an open proxy study remain operationally relevant without outage labels? |
| [Zimmer et al. (2026)](https://doi.org/10.48550/arXiv.2602.21421) | Estimate canopy height over space and time (ECHOSAT) at 10 m resolution from multi-sensor satellite time series and GEDI. | Vision transformer with self-supervised growth loss processing Sentinel-2 time series and GEDI sparse heights. | Cross-sectional accuracy against spaceborne LiDAR and static airborne LiDAR across Europe. | Direct evidence that satellite time series plus GEDI can model temporal height with self-supervised loss constraints. | No repeat airborne LiDAR validation for temporal growth; no infrastructure corridor evaluation; no maintenance scheduling connection. | Does the self-supervised loss capture actual growth or optical seasonal variation, and does it transfer to corridor risk? |

## What the literature already occupies

The project must not claim that it is the first to forecast vegetation growth
near power lines. Mongus et al. and Chen et al. already do this with airborne or
UAV LiDAR. It must not claim the first satellite-based power-line risk map;
Yung et al. already report that direction. It must not claim the first
vegetation-aware trimming optimizer; Jaramillo-Leon and Leite already formulate
one, and Jumbo and Moghaddass already connect image-derived risk to routing and
crew allocation.

Sentinel-2 plus GEDI canopy-height mapping is also mature. Lang et al. establish
a global single-year probabilistic model, Pauls et al. extend the idea to
monthly time-series inputs and annual height maps, and Zimmer et al. (2026,
ECHOSAT) train a vision transformer with self-supervised growth loss across
multi-sensor satellite time series and GEDI. The project therefore must not
claim the first temporal Sentinel-2 plus GEDI canopy-height model.

The broad end-to-end integration claim is now occupied as well. Jumbo and
Moghaddass connect image-derived risk to routing, Ding et al. report an explicit
measurement-assessment-scheduling framework, and Ayobo et al. propose a digital
twin for predictive vegetation management. Parent et al. and Sokolovsky et al.
also show operationally grounded asset-risk modeling. CanopyGuard-AI therefore
must contribute a stronger open evaluation protocol, not claim the first
integrated system.

## Provisional gap for CanopyGuard-AI

No reviewed study yet demonstrates the exact evidence chain below in one open,
reproducible evaluation:

1. Free, repeatable Sentinel-2 time series as the dense temporal signal.
2. Quality-filtered GEDI as sparse height reference.
3. Repeat airborne LiDAR kept out of ordinary model features and used as an
   independent before-and-after validation source.
4. A cited ecological prior whose contribution is measured by an ablation.
5. Uncertainty-aware corridor prioritization connected to a constrained
   maintenance schedule, evaluated against simple scheduling baselines.
6. Public chronological and spatial splits, simple baselines, and a rerunnable
   experiment package.

This gap is `SUPPORTED`, not `CONFIRMED`. The 2025-2026 additions make the claim
narrower and more defensible: the contribution is the open, leakage-resistant
evaluation and independent validation, not component integration. It will be
falsified if an earlier system has the same evidence chain, or if the Sonoma
data cannot distinguish useful future-height ranking from disturbance and
sensor error.

## Consequences for the experiment design

- Airborne LiDAR must remain independent validation truth. Training on the 2022
  validation surface would weaken the central claim.
- The canopy-height benchmark needs at least a simple local Random Forest, a
  no-change or persistence baseline, and a comparison with an available global
  canopy-height product before any deep model is justified.
- Splits must be chronological and spatial. Random pixel splits would leak
  nearby forest structure and overstate generalization.
- Evaluation must report MAE, RMSE, bias, and error by height class. Optical
  height estimates often fail differently for low and tall canopy.
- The temporal result must separate growth from abrupt loss caused by fire,
  harvest, or other disturbance. Slow growth may be smaller than model error.
- Scheduling must compare forecast-driven priority with random, current-height,
  static-risk, and simple highest-risk-first baselines.
- The final claim should be about a tested, reproducible decision pipeline, not
  about regulatory clearance or survey-grade encroachment detection.

## Growth and disturbance evidence added

The Sonoma vegetation map confirms that the study box contains Douglas-fir,
coast redwood, California black oak, other oak alliances, madrone, bay, pine,
and riparian tree classes. USDA growth evidence supports broad, age-dependent
height plausibility ranges for Douglas-fir, redwood, and California black oak.
It does not support one constant for the mixed forest. The numeric evidence and
its permitted use are recorded in `reports/phase1_data_protocol.md`.

Kennedy et al. (2010) support annual Landsat trajectory segmentation for
separating abrupt disturbance, recovery, and longer-duration change. The Phase
1 protocol therefore combines CAL FIRE and MTBS fire evidence with an
independent annual Landsat change screen and a stratified visual audit. Pixels
with disagreeing evidence remain uncertain rather than being labelled stable.

## Remaining review work

1. Expand citation chaining from this core set into a documented systematic
   search before making any absolute novelty statement.
2. Expand the Sonoma growth table beyond the three alliances with defensible
   numeric evidence and add local climate/site transfer checks.
3. Verify whether any study combines open satellite time series, independent
   repeat LiDAR, biological priors, and maintenance optimization.
4. Calibrate and validate the disturbance-screening thresholds on labelled
   Sonoma audit samples.
5. Revisit the locked research question only if new evidence falsifies its
   open-evaluation contribution.

## Rerun inputs

```text
workflow: firecrawl-research-papers
topic: power-line vegetation monitoring, canopy-height time series, growth forecasting, and trimming optimization
target_count: 25 to 35 primary studies plus recent reviews
output: markdown comparison table and synthesis
fallback_used: primary-source web research because Firecrawl was unavailable
```
