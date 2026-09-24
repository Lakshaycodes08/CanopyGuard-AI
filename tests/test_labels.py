from __future__ import annotations

import numpy as np
import pytest

from canopyguard.lidar.labels import CELL_ID_ROW_BASE, cell_id, cell_labels

TRANSFORM = (1.0, 0.0, 510000.0, 0.0, -1.0, 4270020.0)


def test_cell_id_is_unique_and_checked():
    assert cell_id(51000, 427001) == 51000 * CELL_ID_ROW_BASE + 427001
    with pytest.raises(ValueError, match="out of range"):
        cell_id(-1, 0)


def test_labels_sit_on_the_global_grid():
    start = np.zeros((20, 30))
    table = cell_labels(start, start, TRANSFORM, 10.0)
    assert table["cell_id"].size == 6
    assert table["x"][0] == 510005.0 and table["y"][0] == 4270015.0
    assert table["y"][-1] == 4270005.0
    assert table["cell_id"][0] == cell_id(51000, 427001)


def test_labels_carry_mean_percentile_maximum_and_change():
    start = np.full((10, 10), 5.0)
    end = np.full((10, 10), 6.0)
    end[0, 0] = 20.0
    start[9, 9] = np.nan
    table = cell_labels(start, end, TRANSFORM, 10.0)
    assert table["max_end"][0] == 20.0
    assert table["max_change"][0] == pytest.approx(15.0)
    assert table["mean_change"][0] == pytest.approx(np.mean(end) - 5.0, abs=0.01)
    assert table["valid_start"][0] == pytest.approx(0.99)
    assert table["canopy_share"][0] == pytest.approx(1.0)


def test_labels_count_loss_and_blank_thin_cells():
    start = np.full((10, 10), 10.0)
    end = start.copy()
    end[:5] = 1.0
    thin = np.full((10, 10), np.nan)
    thin[0, 0] = 3.0
    assert cell_labels(start, end, TRANSFORM, 10.0)["loss_share"][0] == 0.5
    assert np.isnan(cell_labels(thin, thin, TRANSFORM, 10.0)["mean_start"][0])


def test_labels_reject_an_off_grid_corner():
    with pytest.raises(ValueError, match="global grid"):
        cell_labels(np.zeros((10, 10)), np.zeros((10, 10)),
                    (1.0, 0.0, 510003.0, 0.0, -1.0, 4270020.0), 10.0)
    with pytest.raises(ValueError, match="whole multiple"):
        cell_labels(np.zeros((10, 10)), np.zeros((10, 10)), TRANSFORM, 2.5 * 1.1)
