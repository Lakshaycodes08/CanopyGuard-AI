from __future__ import annotations

import numpy as np
import pandas as pd

from canopyguard.data.climate import aggregate_monthly_climate, calculate_gdd


def test_calculate_gdd() -> None:
    tmax = np.array([25.0, 10.0, 5.0])
    tmin = np.array([15.0, 6.0, 1.0])
    gdd = calculate_gdd(tmax, tmin, base_temp=10.0)
    assert np.isclose(gdd[0], 10.0)
    assert np.isclose(gdd[1], 0.0)
    assert np.isclose(gdd[2], 0.0)


def test_aggregate_monthly_climate() -> None:
    daily_data = pd.DataFrame(
        [
            {
                "segment_id": "seg_001",
                "date": "2023-06-01",
                "prcp_mm": 5.0,
                "tmax_c": 28.0,
                "tmin_c": 16.0,
            },
            {
                "segment_id": "seg_001",
                "date": "2023-06-02",
                "prcp_mm": 10.0,
                "tmax_c": 30.0,
                "tmin_c": 18.0,
            },
        ]
    )
    monthly = aggregate_monthly_climate(daily_data)
    assert len(monthly) == 1
    june = monthly.iloc[0]
    assert np.isclose(june["prcp_sum_mm"], 15.0)
    assert np.isclose(june["tmean_c"], 23.0)
    assert np.isclose(june["gdd_sum"], 26.0)
