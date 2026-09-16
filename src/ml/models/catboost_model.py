from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
from catboost import CatBoostClassifier

from src.ml.models.common import ModelBundle


def fit_catboost(
    frame: pd.DataFrame,
    y,
    *,
    target: str,
    feature_columns: List[str],
    categorical_columns: List[str],
    params: Dict[str, Any],
) -> ModelBundle:
    data = frame.reindex(columns=feature_columns).copy()
    medians: Dict[str, float] = {}
    for column in categorical_columns:
        data[column] = data[column].fillna("__missing__").astype(str)
    for column in feature_columns:
        if column in categorical_columns:
            continue
        values = pd.to_numeric(data[column], errors="coerce")
        median = float(values.median()) if values.notna().any() else 0.0
        medians[column] = median
        data[column] = values.fillna(median)

    model_params = dict(params)
    model_params.setdefault("loss_function", "MultiClass" if target == "1x2" else "Logloss")
    model_params.setdefault("allow_writing_files", False)
    estimator = CatBoostClassifier(**model_params)
    estimator.fit(data, y, cat_features=categorical_columns)
    return ModelBundle(
        model_type="catboost",
        target=target,
        feature_columns=feature_columns,
        categorical_columns=categorical_columns,
        model=estimator,
        numeric_medians=medians,
        classes=[int(value) for value in estimator.classes_],
    )

