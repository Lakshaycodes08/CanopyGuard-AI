"""Training-fold-only stage-one residual models for the 2013 forecast check."""

from __future__ import annotations

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from canopyguard.forecasting.growth_prior import training_scope


def fold_prior(frame, start, end, train, minimum: int) -> np.ndarray:
    """Assign each row a prior increment learned only from training cells."""
    groups = frame["model_group"].to_numpy()
    broad = frame["broader_group"].to_numpy()
    increments = np.full(len(frame), np.nan)
    cache = {}
    for group in np.unique(groups):
        use = groups == group
        broad_group = broad[np.flatnonzero(use)[0]]
        if not np.all(broad[use] == broad_group):
            raise ValueError(f"Multiple broad groups for model group {group}")
        scope, fit_rows = training_scope(
            group, broad_group, train, groups, broad, minimum
        )
        if scope not in cache:
            cache[scope] = float(np.median(end[fit_rows] - start[fit_rows]))
        increments[use] = cache[scope]
    if not np.isfinite(increments).all():
        raise ValueError("Some cells lack a training-fold median increment")
    return increments


def _preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    return ColumnTransformer(
        [
            (
                "numeric",
                make_pipeline(SimpleImputer(strategy="median"), StandardScaler()),
                numeric,
            ),
            ("vegetation", OneHotEncoder(handle_unknown="ignore"), categorical),
        ]
    )


def fit_fold_models(
    frame, residual, train, test, settings: dict, seed: int, models: tuple[str, ...]
) -> tuple[dict[str, np.ndarray], dict[str, dict[str, float]]]:
    """Fit the frozen model families once each on a training fold."""
    from lightgbm import LGBMRegressor

    numeric = settings["numeric_features"]
    categorical = settings["categorical_features"]
    features = frame[numeric + categorical]
    encoder = _preprocessor(numeric, categorical)
    x_train = encoder.fit_transform(features.loc[train])
    x_test = encoder.transform(features.loc[test])
    names = encoder.get_feature_names_out().tolist()
    predictions = {}
    importance = {}
    for name in models:
        if name == "ridge":
            model = Ridge(alpha=settings["ridge"]["alpha"])
        elif name == "lightgbm":
            model = LGBMRegressor(random_state=seed, **settings["lightgbm"])
        else:
            raise ValueError(f"Unregistered stage-two model: {name}")
        model.fit(x_train, residual[train])
        predictions[name] = model.predict(x_test)
        values = (
            model.coef_
            if name == "ridge"
            else model.booster_.feature_importance(importance_type="gain")
        )
        importance[name] = dict(zip(names, map(float, values), strict=True))
    return predictions, importance
