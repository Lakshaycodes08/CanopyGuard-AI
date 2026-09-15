# Phase 1 evidence and one-tile data protocol

Updated: 2026-09-15

## Decision

Status: CONDITIONAL GO

The first Sentinel-2 tile and its catalogue contract are now fixed. Growth-prior
evidence is sufficient for three mapped alliances, and a reproducible
disturbance screen is specified. The DVC-recorded manifest contains 458 valid
tile-10SEH acquisitions across 2017-2022. The phase does not pass yet because no
raster cube has been downloaded, aligned, masked, or checked for clear
observations.

## Vegetation evidence

The 2013 Sonoma County fine-scale vegetation service is an 82-class,
NVC-aligned map built with field data, image segmentation, machine learning,
manual editing, and expert review. A spatial query against the confirmed study
box returned the following tree targets, among others:

- `Pseudotsuga menziesii` and `Sequoia sempervirens`
- `Arbutus menziesii` and `Umbellularia californica`
- coast live oak, blue oak, Oregon white oak, California black oak, valley oak,
  canyon live oak, interior live oak, and a mixed-oak mapping class
- knobcone pine, ponderosa pine and Douglas-fir, gray pine, Monterey pine,
  bigleaf maple, California buckeye, and Fremont cottonwood

Source: [Sonoma Veg Map layer](https://socogis.sonomacounty.ca.gov/map/rest/services/OWTSPublic/Sonoma_Veg_Map_Vegetation_and_Habitat/MapServer/0)

This establishes presence, not species purity at 10 m. Mixed crowns and map
error prevent assigning a single species rate to every pixel.

## Growth-prior evidence table

| Mapped class | Measurement basis | Published height evidence | Permitted use |
| --- | --- | --- | --- |
| Coast Douglas-fir | USDA synthesis of site and age studies | On a medium, low-elevation site, annual height increment is about 0.61 m at age 30, 0.15 m at age 100, and 0.09 m at age 120. | Weak, age-aware prior for Douglas-fir pixels only. Do not use 0.61 m/year as a universal rate. |
| Coast redwood | Dominant young-growth height ranges on good sites | Heights of 30.5-45.7 m at age 50 and 50.3-67.1 m at age 100 imply broad site-matched interval averages of 0.61-0.91 m/year from 0-50 and about 0.40-0.43 m/year from 50-100. | Weak prior for redwood pixels only; the source states fastest height growth occurs before age 35. |
| California black oak | 393 dominant trees in northern and central California | Heights of 8, 13, 17, 22, and 25 m at ages 20, 40, 60, 100, and 140 imply interval averages of 0.25, 0.20, 0.125, and 0.075 m/year. | Weak, age-aware prior for the California black oak alliance only. Do not transfer it to the mixed-oak class. |
| Other mapped tree classes | Presence verified, local height-rate evidence incomplete | No defensible numeric rate locked yet. | No species-specific numeric prior until a primary source and transfer argument are recorded. |

Sources: [Douglas-fir](https://research.fs.usda.gov/silvics/douglas-fir),
[redwood](https://research.fs.usda.gov/silvics/redwood), and
[California black oak](https://research.fs.usda.gov/silvics/california-black-oak)
in USDA Forest Service *Silvics of North America*.

These values are biological plausibility information, not training labels. The
model must compare no-prior and prior variants. If age or defensible age proxies
are unavailable, the age-conditioned numbers must not be collapsed into one
constant.

## Disturbance-screening protocol

The stable-growth subset and the disturbance challenge subset have different
roles. The stable subset supports growth evaluation. The challenge subset tests
whether risk outputs behave sensibly around abrupt change; it is not evidence
that vegetation caused a fire.

1. Restrict the candidate stable subset to mapped tree vegetation with valid
   2013 and 2022 canopy-height coverage.
2. Mark any pixel intersecting a 2013-2022 CAL FIRE wildfire or prescribed-fire
   perimeter as fire affected. CAL FIRE is the primary state record, but its
   published incompleteness and generalization warning must remain attached.
3. Use MTBS burn boundaries and severity as a second fire source. MTBS is not a
   complete fire census because its western mapping target is generally fires
   of at least 1,000 acres.
4. Use an annual Landsat trajectory product or a reproducible LandTrendr run to
   flag non-fire canopy loss, harvest, conversion, or recovery between the
   LiDAR epochs. Thresholds must be calibrated on labelled audit samples, not
   copied from another region.
5. A stable pixel must pass all available screens. Disagreement becomes
   `uncertain_disturbance`, not stable. Keep a stratified visual audit using
   annual imagery and report an error matrix for the screen.
6. Record counts and area before and after each exclusion. Retain excluded
   pixels in a separate disturbance challenge set.

LandTrendr is appropriate because it fits annual Landsat spectral trajectories
and represents abrupt disturbance, recovery, and longer-duration change. Its
authors also show that image misregistration is an important error source, so
co-registration checks are required before interpreting change.

Sources: [LandTrendr paper](https://doi.org/10.1016/j.rse.2010.07.008),
[CAL FIRE fire perimeters](https://www.fire.ca.gov/what-we-do/fire-resource-assessment-program/fire-perimeters),
and [MTBS methods](https://mtbs.gov/mapping-methods).

## First one-tile ingestion contract

The reference corridor, CEC feature 671, falls within Sentinel-2 MGRS tile
`10SEH`. The initial contract is in `configs/ingestion.yaml`.

| Contract field | Decision |
| --- | --- |
| Source | Copernicus Data Space STAC, Sentinel-2 Level-2A |
| Search extent and dates | Read from `configs/study_area.yaml` |
| Tile | `MGRS-10SEH` |
| Catalogue screen | Tile cloud cover at or below 20 percent; not treated as a pixel-clear guarantee |
| Spectral assets | Blue, green, red, NIR at 10 m; red-edge, narrow NIR, and SWIR at 20 m |
| Quality asset | SCL at 20 m |
| Pixel exclusions | SCL 0, 1, 2, 3, 7, 8, 9, 10, and 11 |
| Target grid | EPSG:32610 at 10 m |
| Resampling | Bilinear for reflectance; nearest for SCL |
| First output | Dated scene manifest in `data/interim/sentinel2/mgrs-10seh/` |

The manifest stage validates required assets, filters the configured tile and
cloud limit, deduplicates item identifiers, follows same-origin GET pagination,
and sorts acquisitions chronologically. It does not call the result a data cube.

The 2026-09-15 run retained 458 items and 11 required assets per item. Temporal
coverage runs from 2017-03-01 to 2022-12-18, with annual counts of 47, 68, 84,
91, 81, and 87. The output is recorded by the `sentinel2_manifest` DVC stage.

Copernicus documents SCL classes 0-11 and notes known cloud-classification
limitations. Clear-observation counts must therefore be measured after pixel
masking, not inferred from tile cloud metadata.

Sources: [Copernicus STAC guide](https://documentation.dataspace.copernicus.eu/notebook-samples/geo/migration_of_opensearch_to_stac_guide.html)
and [Sentinel-2 scene classification](https://sentiwiki.copernicus.eu/web/s2-processing).

## Exit checks for the next task

The one-tile cube task is complete only when:

1. the manifest is generated and DVC records it;
2. all configured assets are downloaded or read reproducibly;
3. reflectance scaling and processing-baseline offsets are handled;
4. SCL is resampled with nearest-neighbour and the cloud mask is visually checked;
5. the target grid exactly matches the declared CRS, resolution, bounds, and transform;
6. per-pixel clear-observation counts are reported by month and year; and
7. a small rendered sample passes visual quality assurance.
