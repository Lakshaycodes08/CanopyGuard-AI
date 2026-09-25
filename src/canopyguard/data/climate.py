from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_gdd(
    tmax: np.ndarray, tmin: np.ndarray, base_temp: float = 10.0
) -> np.ndarray:
    """Calculate Growing Degree Days (GDD) from min and max temperatures."""
    tmean = (tmax + tmin) / 2.0
    gdd = tmean - base_temp
    return np.maximum(0.0, gdd)


def aggregate_monthly_climate(daily_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily segment climate data into monthly summary statistics."""
    if daily_df.empty:
        return pd.DataFrame()

    df = daily_df.copy()
    df["month"] = pd.to_datetime(df["date"]).dt.to_period("M").astype(str)

    tmax_arr = df["tmax_c"].to_numpy()
    tmin_arr = df["tmin_c"].to_numpy()
    df["gdd"] = calculate_gdd(tmax_arr, tmin_arr)
    df["tmean_c"] = (df["tmax_c"] + df["tmin_c"]) / 2.0

    grouped = df.groupby(["segment_id", "month"], as_index=False).agg(
        prcp_sum_mm=("prcp_mm", "sum"),
        tmax_mean_c=("tmax_c", "mean"),
        tmin_mean_c=("tmin_c", "mean"),
        tmean_c=("tmean_c", "mean"),
        gdd_sum=("gdd", "sum"),
    )
    return grouped
