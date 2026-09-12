from __future__ import annotations

import random
from collections.abc import Sequence
from datetime import date

import numpy as np


def set_seeds(seed: int) -> None:
    """Seed common random number generators used in experiments."""
    random.seed(seed)
    np.random.seed(seed)

    try:
        import torch
    except ImportError:
        return

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def validate_time_split(
    train_dates: Sequence[date],
    test_dates: Sequence[date],
) -> None:
    """Ensure test data is strictly after training data."""
    if not train_dates or not test_dates:
        msg = "Train and test dates must both be non-empty."
        raise ValueError(msg)

    if min(test_dates) <= max(train_dates):
        msg = "Invalid time split: test data must be after all training data."
        raise ValueError(msg)
