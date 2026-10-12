from __future__ import annotations

import pytest

from canopyguard.config import load_config
from canopyguard.features.lidar import select_lidar_feature_epoch


@pytest.fixture
def lidar_config():
    return load_config("configs/lidar.yaml")


def test_2013_lidar_can_be_a_feature_after_its_survey(lidar_config):
    survey = select_lidar_feature_epoch(lidar_config, "2013", "2013-11-26")
    assert survey["name"] == "2013"


def test_2022_lidar_can_be_a_feature_after_its_survey(lidar_config):
    survey = select_lidar_feature_epoch(lidar_config, "2022", "2022-11-11")
    assert survey["name"] == "2022"


@pytest.mark.parametrize(
    ("epoch", "cutoff"),
    [("2013", "2013-11-25"), ("2022", "2013-11-26")],
)
def test_lidar_acquired_after_cutoff_cannot_be_a_feature(lidar_config, epoch, cutoff):
    with pytest.raises(ValueError, match="ends after prediction cutoff"):
        select_lidar_feature_epoch(lidar_config, epoch, cutoff)


def test_unknown_lidar_epoch_cannot_be_a_feature(lidar_config):
    with pytest.raises(ValueError, match="Unknown LiDAR epoch"):
        select_lidar_feature_epoch(lidar_config, "2024", "2025-01-01")


def test_lidar_without_an_end_date_cannot_be_a_feature(lidar_config):
    del lidar_config["epochs"][0]["end"]
    with pytest.raises(ValueError, match="needs a valid end date"):
        select_lidar_feature_epoch(lidar_config, "2013", "2014-01-01")


def test_prediction_cutoff_must_be_a_full_date(lidar_config):
    with pytest.raises(ValueError, match="prediction_cutoff must use YYYY-MM-DD"):
        select_lidar_feature_epoch(lidar_config, "2013", "2013")
