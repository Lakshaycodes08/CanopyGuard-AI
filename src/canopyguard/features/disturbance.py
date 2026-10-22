"""Flag disturbance after the cutoff from the change in Landsat NBR.

The flag looks at the future relative to the forecast cutoff, so it screens
training and scoring rows and is never a predictor. Smoke, haze and phenology
move NBR a little, so the threshold is a published change level, not a value
tuned against the LiDAR labels.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from canopyguard.features.landsat_history import yearly_indices


def nbr_drop(
    pre: NDArray[np.float32], post: NDArray[np.float32], config: dict[str, Any]
) -> dict[str, NDArray[np.float32]]:
    """NBR loss against the pre-cutoff baseline, as (row, column) rasters.

    `final` averages the last years of the window, so it keeps persistent loss
    such as fire scars and cuts and drops short dips. `peak` is the worst year.
    """
    baseline = np.nanmean(
        yearly_indices(pre)["nbr"][-int(config["baseline_years"]) :], axis=0
    )
    drop = baseline[None] - yearly_indices(post)["nbr"]
    final = np.nanmean(drop[-int(config["final_years"]) :], axis=0)
    return {
        "sat_nbr_drop_final": final.astype(np.float32),
        "sat_nbr_drop_peak": np.nanmax(drop, axis=0).astype(np.float32),
    }


def satellite_disturbed(
    final_drop: NDArray[np.float32], threshold: float
) -> NDArray[np.float32]:
    """1 where the persistent NBR loss reaches the threshold, 0 where it does
    not, NaN where there is no clear observation."""
    flag = (final_drop >= threshold).astype(np.float32)
    flag[~np.isfinite(final_drop)] = np.nan
    return flag
