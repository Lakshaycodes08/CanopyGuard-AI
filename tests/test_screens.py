import numpy as np
import pandas as pd
import pytest

from canopyguard.features.disturbance import nbr_drop, satellite_disturbed
from canopyguard.forecasting.growth_model import NON_FEATURES
from canopyguard.forecasting.region_transfer import apply_screen
from canopyguard.forecasting.screen_check import agreement, kept_and_removed


def composites(nbr_values):
    """Composites (year, band, 1, 1) whose NBR equals each requested value."""
    out = np.zeros((len(nbr_values), 6, 1, 1), dtype=np.float32)
    for i, nbr in enumerate(nbr_values):
        out[i, 3] = 1.0 + nbr
        out[i, 5] = 1.0 - nbr
    return out


def test_persistent_nbr_loss_is_flagged_and_a_short_dip_is_not():
    config = {"baseline_years": 3, "final_years": 2}
    pre = composites([0.6, 0.6, 0.6])
    lost = nbr_drop(pre, composites([0.6, 0.2, 0.2, 0.2]), config)
    dipped = nbr_drop(pre, composites([0.6, 0.2, 0.6, 0.6]), config)
    assert lost["sat_nbr_drop_final"][0, 0] == pytest.approx(0.4, abs=1e-5)
    assert dipped["sat_nbr_drop_peak"][0, 0] == pytest.approx(0.4, abs=1e-5)
    assert satellite_disturbed(lost["sat_nbr_drop_final"], 0.10)[0, 0] == 1.0
    assert satellite_disturbed(dipped["sat_nbr_drop_final"], 0.10)[0, 0] == 0.0
    nothing = np.array([[np.nan]], dtype=np.float32)
    assert np.isnan(satellite_disturbed(nothing, 0.10)[0, 0])


def test_screens_and_checks_are_never_predictors():
    for name in (
        "sat_nbr_drop_final",
        "sat_nbr_drop_peak",
        "sat_disturbed",
        "echosat_drop_share",
        "burned",
    ):
        assert name in NON_FEATURES


def test_satellite_screen_drops_unflagged_missing_and_burned_rows():
    table = pd.DataFrame(
        {
            "burned": [0.0, 0.0, 0.0, 1.0],
            "sat_disturbed": [0.0, 0.5, np.nan, 0.0],
        }
    )
    rule = {"max_burned_share": 0.0, "max_sat_disturbed_share": 0.1}
    assert apply_screen(table, rule).index.tolist() == [0]


def test_kept_and_removed_compare_against_echosat():
    table = pd.DataFrame(
        {
            "echosat_drop_share": [0.0, 0.0, 0.5, np.nan],
            "loss_share": [0.0, 0.0, 0.6, 0.9],
        }
    )
    kept = np.array([True, True, False, True])
    result = kept_and_removed(table, kept, echosat_threshold=0.1)
    assert result["kept"]["echosat_abrupt_loss_rows"] == 0.0
    assert result["removed"]["echosat_abrupt_loss_rows"] == 1.0
    assert result["kept"]["rows"] == 2


def test_agreement_reports_precision_and_recall():
    flag = np.array([True, True, False, False])
    truth = np.array([True, False, True, False])
    result = agreement(flag, truth)
    assert result["precision"] == pytest.approx(0.5)
    assert result["recall"] == pytest.approx(0.5)


def test_compact_echosat_copy_keeps_block_means_and_missing_blocks():
    from canopyguard.data.echosat_drop import compact_percent, expand_percent

    share = np.zeros((6, 6), dtype=np.float32)
    share[:3, :3] = 0.5
    share[3:, 3:] = np.nan
    percent = compact_percent(share, 3)
    assert percent.tolist() == [[50, 0], [0, 255]]
    back = expand_percent(percent, 3, (6, 6))
    assert back[0, 0] == pytest.approx(0.5)
    assert back[0, 4] == 0.0
    assert np.isnan(back[5, 5])
    assert expand_percent(percent, 3, (7, 7)).shape == (7, 7)
