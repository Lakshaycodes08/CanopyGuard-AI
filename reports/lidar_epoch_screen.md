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

## Coverage probes

A published acquisition bounding box is the hull of its work units, not its
coverage. Ten bounding-box queries against the OpenTopography catalogue
establish where each 3DEP acquisition is actually returned.

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

## Consequences

The 2022 acquisition covers the whole study area. The 2023 acquisition does
not. Its southern limit falls between 38.78 and 38.80, so it clips only the
northern edge of the study bounding box, a strip about 0.03 degrees tall.

The noise floor is measured from the 2022 and 2023 pair. That measurement
therefore runs on the intersection of the two acquisitions rather than on the
study area. The intersection spans -123.39 to -122.36 in longitude and 38.79
to 38.93 in latitude, about 15.6 km by 89.2 km, or 1,388 km2 before
work-unit gaps and non-forest cover are removed.

Measurement error is a property of the sensors and the terrain, not of the
study boundary, so calibrating outside the boundary is valid provided the
strata match. The calibration sample is stratified by vegetation group, slope
band and canopy height class to the composition of the study area, and the
per-stratum cell counts are checked against the minimum in
`configs/lidar.yaml` before the measurement is accepted.

This also reorders the work. The noise floor no longer depends on the
study-area fetch, so the gate that decides whether span-scale change is
detectable is reached after downloading two epochs over the calibration band
rather than three epochs over the study area.

## Pending

- Work-unit level coverage inside the calibration band. The probes establish
  presence per box, not per tile.
- Per-stratum cell counts, which require the vegetation and terrain layers.
- 2007 remains excluded. Admitting it for conifer alliances only would need
  its density and vertical datum confirmed from the source metadata.
