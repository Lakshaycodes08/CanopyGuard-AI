"""One-shot test on LiDAR that no model or screen ever saw.

Models are fitted on the training regions only. The reserved tiles are scored
once, against change that runs to the latest survey. Growth to a later survey
spans more years, so predictions are also shown stretched by the ratio of the
two intervals, under the assumption that growth is roughly linear in time.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray


def survey_midpoint(epoch: dict[str, Any]) -> date:
    start = date.fromisoformat(epoch["start"])
    end = date.fromisoformat(epoch["end"])
    return start + (end - start) / 2


def years_between(epochs: list[dict[str, Any]], pair: tuple[str, str]) -> float:
    """Years between the middle dates of the two surveys of a pair."""
    by_name = {e["name"]: e for e in epochs}
    first, last = (survey_midpoint(by_name[name]) for name in pair)
    return (last - first).days / 365.25


def stretch_predictions(
    predictions: dict[str, NDArray[np.float64]],
    ratio: float,
    unchanged: tuple[str, ...] = ("zero",),
) -> dict[str, NDArray[np.float64]]:
    """Scale growth predictions by the interval ratio; no-change stays zero."""
    return {
        name: values if name in unchanged else values * ratio
        for name, values in predictions.items()
    }


def stack_train_test(
    train: pd.DataFrame, test: pd.DataFrame
) -> tuple[pd.DataFrame, NDArray[np.int64]]:
    """Training rows first, test rows after, with fold 0 and fold 1.

    Held-out predictions for fold 1 come from models fitted on fold 0 only.
    """
    table = pd.concat([train, test], ignore_index=True)
    folds = np.concatenate(
        [np.zeros(len(train), dtype=np.int64), np.ones(len(test), dtype=np.int64)]
    )
    return table, folds
