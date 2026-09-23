# LiDAR epoch screen and coverage probes

Run: 2026-09-23

## Epoch admission

Screen thresholds are in `configs/lidar.yaml` under `admission_screen`.
Produced by `scripts/screen_epochs.py`.

| Epoch | Admitted | Failures |
| --- | --- | --- |
| 2013 | yes | none |
| 2022 | yes | none |
| 2023 | yes | none |
| 2007 | no | density unknown, geoid not declared, start and end outside the leaf-on window, excluded in config |

Three epochs are admitted. Their densities are 13.73, 21.51 and 21.32 points
per square metre. The sparsest admitted epoch sets the common density, so
every epoch is thinned to 13.73 points per square metre with a Poisson-disk
radius of 0.2699 m before any surface is built.

2007 is a spring acquisition. Deciduous canopy in that epoch is not comparable
with the three autumn epochs, and its density and vertical datum are not
declared in the catalogue record.

## Coverage

A published acquisition bounding box is the hull of its work units, not its
coverage. Ten bounding-box queries against the OpenTopography catalogue
establish where each 3DEP acquisition is returned.

| Probe box, west south east north | 2022 | 2023 |
| --- | --- | --- |
| -122.88, 38.48, -122.76, 38.55 | yes | no |
| -122.90, 38.60, -122.80, 38.75 | yes | no |
| -122.88, 38.62, -122.76, 38.69 | yes | no |
| -122.88, 38.69, -122.76, 38.71 | yes | no |
| -122.88, 38.73, -122.76, 38.75 | yes | no |
| -122.88, 38.76, -122.76, 38.78 | yes | no |
| -122.90, 38.78, -122.74, 38.82 | yes | yes |
| -122.90, 38.80, -122.74, 38.82 | yes | yes |
| -123.05, 38.83, -122.71, 38.92 | yes | yes |
| -123.39, 38.83, -123.05, 38.92 | yes | yes |

Raw record: `data/interim/lidar/coverage_probes.json`.

A probe answers presence per box, not per work unit, and a box returning both
epochs can still hold no ground carrying both. The per-file bounds in each
project's Entwine source manifest settle it: 4,361 delivered files for 2022
and 8,541 for 2023, each a delivery tile of about 1,290 m.

| Quantity | Value |
| --- | --- |
| Overlapping file pairs | 719 |
| Largest overlap of any pair, shorter side | 645 m |
| Co-covered area | about 51 km2 |
| Squares of 1,000 m wholly inside both | 0 |
| Squares of 500 m wholly inside both | 1 |
| Squares of 250 m wholly inside both | 361 |

645 m is half a delivery tile. The two work units abut, and their tile grids
are offset by half a tile, so what reads as overlap is a seam about 200 km
long and at most half a tile wide.

The same assay was run on every other pair of 3DEP work units whose bounds
touch the study area.

| Pair | Years | Co-covered | 1,000 m squares | 500 m | 250 m |
| --- | --- | --- | --- | --- | --- |
| CA_NorthernCA_1_B22, CA_NorthCoastRanges_2_B23 | 2022, 2023 | 51 km2 | 0 | 1 | 361 |
| CA_NorthCoastRanges_2_B23, CA_NoCAL_Wildfires_TL_QL2_2018 | 2018, 2023 | 27 km2 | 0 | 32 | 313 |
| CA_NorthCoastRanges_2_B23, CA_SolanoCounty_1_A23 | 2023, 2023 | 21 km2 | 0 | 4 | 118 |
| CA_NorthernCA_1_B22, CA_SolanoCounty_1_A23 | 2022, 2023 | 0.8 km2 | 0 | 0 | 5 |
| CA_NorthernCA_1_B22, CA_NoCAL_Wildfires_TL_QL2_2018 | 2018, 2022 | 0 | 0 | 0 | 0 |

No pair admits a single 1,000 m square.

## Consequences

The 2022 acquisition covers the whole study area. The 2023 acquisition does
not, and the two barely meet.

Calibration tiles are 250 m and are derived from the source manifests at run
time. A bounding box drawn around the seam contains mostly single-epoch
ground, so no box is recorded in the configuration.

The aggregation ladder stops at 200 m. A scale wider than the calibration tile
cannot be measured, and coarser scales are extrapolated from the fitted decay
exponent and reported as extrapolated.

Co-registration is solved once over the whole sample. The horizontal offset
belongs to the acquisition pair, and a 250 m tile spans too narrow a range of
aspect to resolve it alone.

Measurement error is a property of the sensors and the terrain, not of the
study boundary, so calibrating on the seam is valid provided the strata match.
The sample is stratified by vegetation group, slope band and canopy height
class to the composition of the study area, and the per-stratum cell counts
are checked against the minimum in `configs/lidar.yaml` before the measurement
is accepted.

## Pending

- Per-stratum cell counts, which require the vegetation and terrain layers.
- Whether any 3DEP pair outside this region carries wide co-coverage one year
  apart, which would extend the measured ladder above 200 m.
- 2007 remains excluded. Admitting it for conifer alliances only would need
  its density and vertical datum confirmed from the source metadata.
