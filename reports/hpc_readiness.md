# NSUT compute and team readiness

Updated: 2026-09-15

## Decision

Heavy data processing and model runs should use shared NSUT infrastructure.
Laptops should hold code, documentation, and small quality-assurance samples,
not the authoritative data workspace.

## Planning storage estimate

The study box is roughly 14 km by 38 km, or about 5.3 million 10 m cells. These
are planning estimates; the exact dimensions will be derived after projecting
and snapping the configured bounds.

| Artifact | Approximate uncompressed size |
| --- | ---: |
| 458 acquisitions, 10 float32 bands clipped to the study box | 90-100 GiB |
| 72 monthly composites, 10 float32 bands | About 15 GiB |
| Monthly clear-count layers | Less than 1 GiB |
| Recommended persistent allocation | At least 300 GiB |
| Recommended scratch allocation | At least 300 GiB |

The recommendation allows room for source rasters, temporary reprojection,
DVC cache entries, model-ready tables, and reruns. It does not justify
downloading complete 100 km Sentinel tiles when clipped reads are possible.

The portable estimator is:

```text
python scripts/estimate_storage.py <dimensions...> --dtype float32 --working-copies 3
```

## Information required from NSUT

- Scheduler name and submission documentation.
- Shared project path, persistent quota, scratch path, and retention policy.
- CPU cores, RAM, job-duration limits, and array-job limits.
- GPU models, VRAM, CUDA drivers, and allocation policy.
- Conda or Mamba availability and supported compiler modules.
- Outbound access to Copernicus, NASA Earthdata, Google Earth Engine, and
  OpenTopography.
- Backed-up filesystem or object storage suitable for a DVC remote.
- Approved secret-storage method. Credentials must not enter Git, DVC metadata,
  shell history, reports, or issue trackers.

## Access request to send

```text
We are running a reproducible geospatial research project using Sentinel-2,
GEDI, and repeat airborne LiDAR. Please provide the scheduler documentation,
project and scratch paths, storage quotas and retention policy, CPU and RAM job
limits, available GPU models and allocation rules, Conda or Mamba availability,
and whether compute nodes have outbound HTTPS access. We expect about 100 GiB
of clipped source imagery and request at least 300 GiB persistent storage plus
300 GiB scratch for reprojection, DVC cache, and reruns. Please also advise the
approved location for access credentials and a backed-up path or object store
suitable for a shared DVC remote.
```

## Scheduler-independent setup

1. Clone the repository into the shared project area.
2. Create the environment only from `environment.yml`.
3. Run the offline test and hygiene checks.
4. Configure one shared DVC remote without committing credentials.
5. Pull DVC data into scratch for jobs; push completed, verified outputs back to
   persistent storage.
6. Run each stage from a clean Git commit and save its commit identifier.

An exact batch script should be added only after the scheduler, modules, paths,
and resource limits are confirmed. This avoids maintaining an untested Slurm or
PBS script that does not match NSUT.

## Team ownership

Assign one named owner to each responsibility. One person may own more than one
area, but every output has exactly one reviewer who did not create it.

| Responsibility | Owner duties | Independent reviewer |
| --- | --- | --- |
| Data and DVC | Ingestion, hashes, provenance, storage, no data in Git | Validation owner |
| Cube quality | CRS, transform, masking, clear counts, rendered samples | Data owner |
| Modeling | Baselines, time/spatial splits, seeds, run logs | Reproducibility owner |
| Validation | LiDAR alignment, disturbance subsets, error analysis | Modeling owner |
| Scheduling | Scenario constraints, baseline comparisons, claim limits | Validation owner |
| Paper and release | Claims log, citations, venue policy, final archive | Whole team |

## Collaboration rule

Code and configs move through Git review. Data and model artifacts move through
DVC. Results are accepted only when another teammate can reproduce the stage
from the recorded Git commit and DVC hashes.
