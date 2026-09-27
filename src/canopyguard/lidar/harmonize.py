"""Epoch admission and the decisions that make two acquisitions comparable."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray


def admit_epoch(epoch: dict[str, Any], screen: dict[str, Any]) -> dict[str, Any]:
    """Apply the admission screen to one epoch and list every failure."""
    failures: list[str] = []

    density = epoch.get("nominal_density_pts_m2")
    if density is None:
        failures.append("density unknown")
    elif density < screen["min_density_pts_m2"]:
        failures.append(f"density {density} below {screen['min_density_pts_m2']}")

    if screen.get("require_declared_vertical_datum") and not epoch.get("geoid"):
        failures.append("geoid not declared")

    months = set(screen["leaf_on_months"])
    for key in ("start", "end"):
        value = epoch.get(key)
        if value is None:
            failures.append(f"{key} date missing")
        elif date.fromisoformat(str(value)).month not in months:
            failures.append(f"{key} outside the leaf-on window")

    return {
        "name": epoch.get("name"),
        "admitted": not failures,
        "failures": failures,
    }


def decimation_target(densities: list[float], floor_pts_m2: float) -> float:
    """Density every epoch is thinned to, which is the sparsest admitted one.

    Denser returns find the canopy apex more often. Leaving epochs at their
    native densities produces apparent height growth of the same order as the
    biological signal, so the comparison is made at a common density.
    """
    usable = [value for value in densities if value is not None and value > 0]
    if not usable:
        raise ValueError("At least one positive density is required")
    target = min(usable)
    if target < floor_pts_m2:
        raise ValueError(f"Sparsest epoch {target} is below the floor {floor_pts_m2}")
    return float(target)


JAMMING_COEFFICIENT = 0.70


def poisson_radius(target_density_pts_m2: float) -> float:
    """Exclusion radius giving the requested mean point density.

    The thinning filter keeps a point when no already-kept point lies within
    the radius, which is random sequential adsorption of hard disks. That
    saturates near 0.70 / r squared rather than 1 / r squared, so the plain
    inverse square root leaves the result about 1.4 times sparser than asked.
    """
    if target_density_pts_m2 <= 0:
        raise ValueError("Target density must be positive")
    return float(np.sqrt(JAMMING_COEFFICIENT / target_density_pts_m2))


def scan_angle_mask(angles_deg: ArrayLike, max_abs_deg: float) -> NDArray[np.bool_]:
    """Keep returns within the shared scan-angle band of both acquisitions."""
    if max_abs_deg <= 0:
        raise ValueError("Scan angle limit must be positive")
    return np.abs(np.asarray(angles_deg, dtype=np.float64)) <= max_abs_deg


def class_mask(
    classifications: ArrayLike, drop_classes: list[int]
) -> NDArray[np.bool_]:
    """Drop noise, water and overlap classes before any surface is built."""
    values = np.asarray(classifications)
    return ~np.isin(values, list(drop_classes))


def retained_fraction(mask: ArrayLike) -> float:
    """Share of returns a mask keeps."""
    values = np.asarray(mask, dtype=bool).ravel()
    if values.size == 0:
        raise ValueError("Mask must be non-empty")
    return float(values.mean())


def screen_epochs(lidar_config: dict[str, Any]) -> list[dict[str, Any]]:
    """Apply the admission screen to every configured epoch."""
    screen = lidar_config["admission_screen"]
    results = [admit_epoch(epoch, screen) for epoch in lidar_config["epochs"]]
    for epoch, result in zip(lidar_config["epochs"], results, strict=True):
        if epoch.get("admitted") is False:
            result["admitted"] = False
            result["failures"] = result["failures"] + ["excluded in config"]
    return results


def admitted_names(results: list[dict[str, Any]]) -> list[str]:
    """Names of the epochs that passed the screen."""
    return [result["name"] for result in results if result["admitted"]]


def sample_radius_for(
    lidar_config: dict[str, Any], results: list[dict[str, Any]]
) -> float:
    """Poisson-disk radius thinning every admitted epoch to a common density."""
    names = set(admitted_names(results))
    densities = [
        epoch["nominal_density_pts_m2"]
        for epoch in lidar_config["epochs"]
        if epoch["name"] in names
    ]
    floor = lidar_config["admission_screen"]["min_density_pts_m2"]
    target = decimation_target(densities, floor)
    return poisson_radius(target)
