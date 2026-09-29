# 2013-2022 label overlap check

Checked 30 September 2026 against the [shared Drive archive](https://drive.google.com/file/d/1aYwj068dBZtFgGOkOU9N2KgNo9BH6fYZ/view). The source SHA-256 is `dc91f03b4f067a54a6666fc15cfdf6b86dc368a1d97e44555fb762515ab10763`.

| Count | Rows |
| --- | ---: |
| Raw archive | 1,719,567 |
| Valid change in both epochs | 1,478,301 |
| Unique valid cells after overlap selection | 1,478,103 |
| Repeated valid rows removed | 198 |

For each global cell ID, the rule keeps the tile with the highest *minimum* coverage across the two epochs. Equal minima are broken by higher total coverage, then lower tile ID. It never chooses a row based on the size or direction of canopy change. Cell IDs with inconsistent coordinates or repeated within one tile cause an error.

All 198 valid overlapping cell pairs differ in at least one change statistic. The largest pairwise differences are 8.13 m for mean change, 17.52 m for 95th-percentile change and 17.58 m for maximum change. The median 95th-percentile disagreement is 0.53 m; 53 pairs differ by more than 1 m, including 17 by more than 3 m. The rule makes the table unique and repeatable; these large disagreements still need spatial inspection before the full archive is accepted as scientific truth. The unique archive marks these cells with `overlap_disputed`; filter them out of an initial model until that review is complete. The independent same-year control also remains open.

The [machine-readable audit](label_quality_2013-2022.json) is a snapshot of counts, rule and hashes. The generated archive and audit stay under ignored `data/processed/`. To reproduce after placing the exact source file at the path in `configs/lidar.yaml`, run `dvc repro label_quality_2013_2022`. The project has no configured DVC remote, so a fresh clone must first obtain the source archive from the linked Drive file and verify its SHA-256.
