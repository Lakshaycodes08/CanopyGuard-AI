"""Compare disturbance screens against each other and against ECHOSAT.

ECHOSAT is an independent, modeled height product. It sees height drops from
2018 on, so it cannot confirm earlier events, and it is used here only to
check the screens, never as a predictor or a screen itself.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from canopyguard.forecasting.hazard_model import auc_roc


def kept_and_removed(
    table: pd.DataFrame, kept: NDArray[np.bool_], echosat_threshold: float
) -> dict[str, dict[str, float]]:
    """ECHOSAT abrupt-loss rate and LiDAR loss for kept and removed rows."""
    seen = table["echosat_drop_share"].notna().to_numpy()
    out = {}
    for name, rows in (("kept", kept), ("removed", ~kept)):
        rows = rows & seen
        drop = table.loc[rows, "echosat_drop_share"]
        out[name] = {
            "rows": int(rows.sum()),
            "echosat_mean_drop_share": float(drop.mean()) if rows.any() else np.nan,
            "echosat_abrupt_loss_rows": float((drop >= echosat_threshold).mean())
            if rows.any()
            else np.nan,
            "lidar_mean_loss_share": float(table.loc[rows, "loss_share"].mean())
            if rows.any()
            else np.nan,
        }
    return out


def agreement(flag: NDArray[np.bool_], truth: NDArray[np.bool_]) -> dict[str, float]:
    """How well one screen's removals match another source's disturbance."""
    hit = float((flag & truth).sum())
    return {
        "precision": hit / max(float(flag.sum()), 1.0),
        "recall": hit / max(float(truth.sum()), 1.0),
        "flagged_share": float(flag.mean()),
        "truth_share": float(truth.mean()),
    }


def drop_auc(table: pd.DataFrame, truth: NDArray[np.bool_]) -> float:
    """AUC of the continuous NBR loss for ranking LiDAR-measured loss rows."""
    ok = table["sat_nbr_drop_final"].notna().to_numpy()
    return auc_roc(table.loc[ok, "sat_nbr_drop_final"].to_numpy(), truth[ok])
