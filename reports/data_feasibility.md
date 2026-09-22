# Phase 0 data feasibility memo

Checked: 2026-09-12

## Decision

Status: GO

The refined northern Sonoma candidate passes all six scientific data gates. It
replaces the earlier one-mile candidate because that small box contained no
mapped fire event for the planned independent check. NASA Earthdata, Google
Earth Engine, and OpenTopography account access are confirmed, so Phase 0 is
complete and the study-area configuration is fixed for Phase 1.

This is a regional feasibility area, not a claim that the final experimental
design is complete. The risk score will be a research prioritization aid, not a
regulatory clearance or safety certification.

## Candidate area

| Field | Value |
| --- | --- |
| Name | Northern Sonoma candidate |
| CRS | EPSG:4326 |
| West | -122.90 |
| South | 38.475 |
| East | -122.74 |
| North | 38.82 |
| Corridor source | California Energy Commission transmission-line layer |
| Corridor selection | PG&E, operational, overhead, 60/115/230 kV |
| Intersecting published features | 41 |
| Reference forested feature | OBJECTID 671 |
| Feasibility buffer | 100 m around the published line |

The published line is approximate context. It is not survey-grade engineering
truth and must not be used to make clearance or safety decisions.

## Six-gate check

### 1. A transmission corridor crosses vegetation: PASS

The California Energy Commission layer contains 41 published operational
overhead PG&E features intersecting the refined box: 11 at 60 kV, 11 at 115 kV,
and 19 at 230 kV. These are source features, not 41 independent corridors.

Reference feature 671 is a 60 kV segment already checked against vegetation.

Canopy-height statistics were queried inside a 300-foot buffer around that
segment. The buffer contains 5,426 sampled 30-foot pixels in each epoch.

| LiDAR epoch | Mean height | Median height | Maximum height |
| --- | ---: | ---: | ---: |
| 2013 | 17.9 ft | 0.0 ft | 145.6 ft |
| 2022 | 19.1 ft | 4.9 ft | 157.1 ft |

The non-zero means and tall maxima show that substantial vegetation exists near
the published corridor. These summary values are feasibility evidence only, not
growth estimates. Pixel-level quality control is required before analysis.

Source: [California Electric Transmission Lines](https://socogis.sonomacounty.ca.gov/map/rest/services/OWTSPublic/California_Electric_Transmission_Lines/MapServer/0)

### 2. Two airborne-LiDAR epochs overlap: PASS

The County of Sonoma publishes canopy-height rasters for 2013 and 2022 over the
candidate. Both services provide 3-foot source pixels in California State Plane
Zone II, so the area has before-and-after canopy-height evidence.

For the exact candidate box, both services were exported to the same coarse
WGS84 verification grid. All 1,271,808 grid cells contained valid values in
both epochs. This confirms complete overlap for the box; it is a coverage check,
not an analysis-ready resampling method.

The 2013 survey was collected in fall 2013. The 2022 product was created at
1-meter resolution and reprojected and resampled to align with the 2013 grid.

Important limitation: the underlying terrain products use different vertical
datum realizations, NAVD88 Geoid 12A in 2013 and Geoid 18 in 2022. The analysis
must compare canopy-height products after quality checks. It must not directly
subtract unmatched raw elevations.

Sources:

- [2013 Sonoma LiDAR collection](https://portal.opentopography.org/datasetMetadata?otCollectionID=OT.092014.2871.1)
- [2013 vegetation-height image service](https://socogis.sonomacounty.ca.gov/image/rest/services/Rasters/Lidar_Intensity_Vegetation_Height_2013/ImageServer)
- [2022 vegetation-height image service](https://socogis.sonomacounty.ca.gov/image2/rest/services/Rasters/Lidar_Vegetation_Height_2022/ImageServer)

### 3. GEDI has sufficient reference shots: PASS

NASA Common Metadata Repository returned 113 GEDI02_A Version 2 granules whose
published spatial metadata intersects the candidate box. Their acquisition
dates run from 2019-05-26 through 2025-06-23. For the configured 2019-2022
period, the annual granule counts are 15, 20, 20, and 26.

An exact Google Earth Engine query then loaded the 108 GEDI02_A Version 2 table
assets intersecting the box and filtered individual footprints to 2019-2022.
The predeclared Phase 0 filter retained `quality_flag = 1`,
`degrade_flag = 0`, and valid sensitivity values from 0 through 1. It returned
63,942 footprints across 54 acquisition dates and 54 orbits, far above the
minimum screen of 500 footprints and three dates.

This count is the result of a catalogue and table query. No GEDI granule has
been downloaded into the data workspace. The Phase 0 filter is deliberately
weak and accepts any sensitivity value. The consensus filter set adopted for
analysis adds night-only acquisition, full-power beams, sensitivity at or
above 0.95 in closed conifer, and a 30 degree slope limit. Compounding those
rates against 63,942 gives an expected retained sample of order 3,000 to
6,000 over 533 km2, which is roughly 6 footprints per km2. Published
stand-level growth work requires at least 40 footprints per km2. The
sensitivity threshold also biases retention toward shorter and less dense
canopy, which is the opposite of the tall stands of operational interest. The
Phase 0 pass therefore stands as a feasibility gate for canopy height
reference data, and GEDI is used as an independent cross-check rather than as
a training target.

Spatial coverage also passes. There were 29,866 quality footprints inside the
exact 2017-2022 MTBS perimeters for Tubbs, Kincade, Walbridge, and Pocket, and
2,132 inside the southern comparison box. A conservative robustness subset
requiring sensitivity at least 0.95, nighttime acquisition, and RH98 from 2 to
60 meters retained 26,858 footprints overall and 13,113 inside the fire
perimeters. The conservative filter is supporting evidence, not the final
Phase 1 training rule.

Sources:

- [NASA GEDI Level 2A Version 2](https://doi.org/10.5067/GEDI/GEDI02_A.002)
- [NASA guidance on GEDI quality filtering](https://forum.earthdata.nasa.gov/viewtopic.php?t=6636)
- [Earth Engine GEDI02_A index](https://developers.google.com/earth-engine/datasets/catalog/LARSE_GEDI_GEDI02_A_002_INDEX)
- [MTBS burned-area boundaries](https://developers.google.com/earth-engine/datasets/catalog/USFS_GTAC_MTBS_burned_area_boundaries_v1)

### 4. Sentinel-2 covers the dates: PASS

The official Copernicus STAC catalogue was queried for Level-2A scenes over the
candidate box with published tile cloud cover at or below 20 percent. It
returned between 139 and 320 scenes per year for the configured 2017-2022
period, with no next page of results. This is sufficient catalogue coverage for
a seasonal time series. Pixel-level cloud masking is still required during
ingestion because tile-level cloud percentage does not guarantee that the
candidate pixels are clear.

| Year | Returned scenes |
| --- | ---: |
| 2017 | 139 |
| 2018 | 263 |
| 2019 | 299 |
| 2020 | 320 |
| 2021 | 290 |
| 2022 | 318 |

Source: [Copernicus Data Space STAC catalogue](https://documentation.dataspace.copernicus.eu/APIs/STAC.html)

### 5. Undisturbed comparison forest exists nearby: PASS WITH LIMITATION

The aligned 2013 and 2022 coverage check found about 17,873 hectares where both
coarse verification cells were at least 10 feet high. This 10-foot screen is a
descriptive feasibility threshold, not a forest definition or model parameter.

The southern sub-box from -122.90, 38.475 to -122.86, 38.525 contains about 751
hectares above the same persistent-canopy screen, and a CAL FIRE spatial query
returned no mapped fire perimeter there. Together, repeated tall canopy and the
fire screen provide positive evidence that comparison forest can be selected.

Absence from the fire database does not rule out logging, disease, storm damage,
or small unrecorded fires. Phase 1 must inspect imagery and exclude disturbed
pixels before any growth analysis.

Source: [CAL FIRE historical fire perimeters](https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/California_Historic_Fire_Perimeters/FeatureServer/0)

### 6. An independent risk-check layer exists: PASS WITH LIMITATION

CAL FIRE publishes a statewide historical fire-perimeter dataset extending back
to 1878. A spatial query returned 38 published perimeters intersecting the
refined box, including the 2017 Tubbs and Pocket fires, the 2019 Kincade Fire,
and the 2020 Walbridge Fire. The layer is suitable for a consistency check, with
the published warning that perimeters may be incomplete or generalized.

Fire overlap is not evidence that vegetation near a line caused a fire. It can
only be used as an independent spatial consistency check unless a stronger
causal record is obtained.

Source: [California Fire Perimeters](https://lab.data.ca.gov/dataset/california-fire-perimeters-all)

## Source decision for transmission lines

The handbook names HIFLD as corridor context. Public HIFLD access changed after
the handbook was written, and publicly mirrored snapshots may be stale. For the
California feasibility check, the current California Energy Commission layer is
the primary corridor source. A dated HIFLD snapshot may still be retained later
as a comparison layer, but its approximate geometry must not be treated as
engineering truth.

## Setup checklist

| Item | Status |
| --- | --- |
| Git repository and CI | PASS |
| Offline tests | PASS |
| DVC initialized | PASS |
| NASA Earthdata account access | PASS - user confirmed successful login on 2026-09-12 |
| Google Earth Engine access | PASS - noncommercial Community Tier registered through 2028-03-12 |
| OpenTopography account access | PASS - registered academic user and data access confirmed by user screenshot on 2026-09-12 |
| DVC remote | PENDING STORAGE DECISION |
| Experiment tracker | PENDING TOOL DECISION |
| Compute | PASS - every required result runs on CPU within the scoped processing footprint |

## Phase 0 exit condition

Phase 0 is GO. The exact GEDI feasibility screen and all other scientific data
gates pass, the required data-service accounts are confirmed, and the exact
study-area configuration is fixed. The predeclared GEDI screen was at least 500
quality-flagged, non-degraded footprints across at least three independent
acquisition dates, with spatial coverage of both disturbed and comparison
portions of the box. This screen confirms feasibility only; the final training
sample size and spatial split will be justified in Phase 1.
