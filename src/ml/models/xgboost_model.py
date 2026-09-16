from __future__ import annotations

from typing import Any, Dict, List

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier

from src.ml.models.common import ModelBundle


def fit_xgboost(
    frame,
    y,
    *,
    target: str,
    feature_columns: List[str],
    categorical_columns: List[str],
    params: Dict[str, Any],
) -> ModelBundle:
    numeric = [name for name in feature_columns if name not in categorical_columns]
    processor = ColumnTransformer(
        [
            (
                "numeric",
                Pipeline([("imputer", SimpleImputer(strategy="median"))]),
                numeric,
            ),
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_columns,
            ),
        ]
    )
    model_params = dict(params)
    model_params.setdefault("n_jobs", -1)
    model_params.setdefault("eval_metric", "logloss")
    estimator = Pipeline(
        [
            ("features", processor),
            ("model", XGBClassifier(**model_params)),
        ]
    )
    estimator.fit(frame[feature_columns], y)
    return ModelBundle(
        model_type="xgboost",
        target=target,
        feature_columns=feature_columns,
        categorical_columns=categorical_columns,
        model=estimator,
        classes=[int(value) for value in estimator.named_steps["model"].classes_],
    )

