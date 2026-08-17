from datetime import date

import pytest

from canopyguard.utils import validate_time_split


def test_validate_time_split_accepts_future_test_dates() -> None:
    validate_time_split(
        train_dates=[date(2023, 1, 1), date(2023, 12, 31)],
        test_dates=[date(2024, 1, 1)],
    )


def test_validate_time_split_rejects_overlap() -> None:
    with pytest.raises(ValueError, match="test data"):
        validate_time_split(
            train_dates=[date(2023, 1, 1), date(2023, 12, 31)],
            test_dates=[date(2023, 6, 1)],
        )
