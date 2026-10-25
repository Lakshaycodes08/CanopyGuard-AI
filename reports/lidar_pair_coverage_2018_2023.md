# 2018 and 2023 LiDAR co-coverage (issue 15)

Run: 2026-10-15. Owner: Rehaan. Coverage check only. It does not measure canopy
change, and 2018 is not an admitted epoch (it has not passed the admission
screen in `configs/lidar.yaml`).

## Answer

Owner decision (2026-10-25): retain the 6.7 km2 area as a possible small,
out-of-area exploratory ECHOSAT change check. Do not present it as validation
inside the northern Sonoma study box or as a headline result. The 2018 epoch
must pass its admission and label-quality checks before any change score is
computed. The 4.8 km2 sensitivity at a 5 m canopy threshold and the terrain
and height differences below must accompany any eventual result.

- One number: **6.7 km2 of usable canopy** where both epochs hold returns. Usable
  means canopy of at least 2 m in both epochs (the repo canopy rule), no loss of
  more than 3 m between them, and outside every fire perimeter of 2018 to 2023.
  It sits on 236 of the 267 shared 250 m tiles.
- Against the issue rule (under about 5 km2, drop the ECHOSAT change test), 6.7
  km2 does not trigger the drop. It is close to the line: 4.8 km2 if only trees
  of at least 5 m count. Without the fire exclusion the 2 m figure is 7.6 km2.
  See Sensitivity. The call belongs to the project owner.
- **None of the shared ground is inside the study box.** The nearest shared patch
  is 42.9 km east of it, and no shared ground lies within 25 km. The shared
  ground is shorter and more open than the box (see Is it similar terrain).

## Shared ground from the file outlines (upper bound)

Source: the 3DEP source manifests, through `lidar.sources.footprint`.

| Quantity | Value |
| --- | --- |
| 2018 survey footprint (CA_NoCAL_Wildfires_TL_QL2_2018) | 549.1 km2, 0.0 km2 inside the study box |
| 2023 survey footprint (CA_NorthCoastRanges_2_B23) | 8,365.0 km2, 6.6 km2 inside the study box |
| Shared by both | 33.5 km2 in 3 patches (16.6, 9.6, 7.3 km2) |
| Shared inside the study box | 0.0 km2 |
| Shared within 5, 10 and 25 km of the study box | 0.0 km2 |
| 250 m tiles wholly inside both | 267 (16.7 km2) |

The earlier screen in `reports/lidar_epoch_screen.md` gave about 27 km2, 32
squares of 500 m and 313 of 250 m for this pair. This run gives 33.5 km2 and 267
tiles of 250 m. The methods differ (this run unions every delivered file and
measures all three patches), and I did not reconcile the two further.

## Shared ground on real returns

`lidar.pair_points` reads every octree node down to depth 12 that meets a shared
tile: 3,048 nodes (89.2 million kept returns) for 2018 and 7,026 nodes (292.1
million) for 2023. A tile is valid for an epoch when at least 90 percent of its
10 m cells hold a return and at least 50 percent hold a ground return.

| Quantity | Value |
| --- | --- |
| Tiles valid in 2018 | 236 of 267 |
| Tiles valid in 2023 | 266 of 267 |
| Tiles valid in both | 236 (14.8 km2 of tiles) |
| Cells with ground and top returns in both | 12.9 km2 |
| Canopy of at least 2 m in both epochs | 8.1 km2 |
| Of that, lost more than 3 m | 0.9 km2 |
| Of that, inside a fire perimeter | 1.2 km2 |
| **Usable canopy (no loss, no fire)** | **6.7 km2** |

The 31 tiles invalid in 2018 hold returns in a median of 71 percent of their
cells, which fits partial coverage or open water. The 2023 survey is dense
everywhere on these tiles.

Fires in the gap (FRAP perimeters, 100 acres and up, meeting the shared region):
COUNTY (2018, 89,831 acres), SAND (2019, 2,422 acres), HENNESSEY (2020, 305,352
acres). The 2018 flight dates are not in the manifests, so a 2018 fire may
already be in the 2018 data. Excluding it is the cautious choice.

## What the shared canopy is made of

Canopy height class of the 8.1 km2 of canopy in both epochs, from 2023:

| Height | km2 |
| --- | --- |
| 2 to 5 m | 1.8 |
| 5 to 15 m | 5.4 |
| 15 to 30 m | 0.9 |
| 30 m and above | 0.005 |

Terrain on the 12.9 km2 with returns in both epochs: median slope 11.9 degrees;
7.4 km2 at 0 to 15 degrees, 4.3 km2 at 15 to 30, 1.1 km2 at 30 or more; ground
elevation 77 m to 525 m, median 134 m. No vegetation-type map covers this ground
(the Sonoma Veg Map ends at the county line), so canopy height class stands in
for vegetation mix.

## Sensitivity

Usable canopy in km2 when one threshold moves and the others stay at the values
above (full table in `reports/lidar_pair_coverage_2018_2023.json`):

| Canopy threshold | 2 m | 3 m | 5 m | 10 m |
| --- | --- | --- | --- | --- |
| Usable canopy km2 | 6.7 | 6.0 | 4.8 | 2.1 |

The result barely moves with the loss limit (2, 3, 5 m: 6.6, 6.7, 6.8 km2), the
cell fraction (0.8, 0.9, 0.95: 6.9, 6.7, 6.5 km2) or the ground fraction. The
canopy threshold is the one that matters.

## Is it similar terrain

Not the same terrain, and not nearby. One check, using ECHOSAT 2023 as a common
yardstick (exploratory, run outside the repo with the ECHOSAT code now on
main, and not part of this script): mean height 6.7 m over the valid
shared tiles against 10.2 m over the study box, and 4 percent of pixels at 15 m
or taller against 22 percent. The shared ground is lower and more open. A change
test there says little about the tall stands of the study box.

## Limits

- Heights are coarse: the highest non-ground return minus the mean ground of a
  10 m cell, using the provider's ground class. The nodes sampled in both epochs
  carry no vegetation classes (3 to 5), so every non-ground return counts as
  surface. This judges coverage and
  canopy extent. It is not the matched canopy height model used to measure
  change.
- Returns come from depth 12 of the octree, which is already near full density
  here but is not the thinned, re-classified input of the change pipeline.
- Tile validity needs returns in 90 percent of cells, so edges and water lower the
  count. Fire perimeters can be incomplete or over-generalized (FRAP).
- This is a coverage check. It says nothing about whether ECHOSAT change matches
  LiDAR change.

## Reproduce

`pip install -e ".[lidar]"` then `python scripts/check_lidar_pair_coverage.py`.
It reads the public point clouds, takes about 25 minutes, and needs network access
to the 3DEP bucket and the FRAP service. Tests are offline. Settings are in the
`pair_coverage` section of `configs/lidar.yaml`.
