from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

import joblib
import mlflow
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, log_loss, roc_auc_score

from db import create_database, database_path, upsert_ml_run
from src.ml.config import artifact_root_uri, artifacts_dir, load_config, tracking_uri
from src.ml.database import DatabaseCatalog
from src.ml.dataset import temporal_split
from src.ml.features import FeatureDataset, build_feature_dataset
from src.ml.models.catboost_model import fit_catboost
from src.ml.models.xgboost_model import fit_xgboost

TARGET_COLUMNS = {"1x2": "target_1x2", "over_2_5": "target_over_2_5"}


def _metrics(y_true, probabilities: np.ndarray, classes: List[int], prefix: str) -> Dict[str, float]:
    predicted = np.asarray(classes)[probabilities.argmax(axis=1)]
    result = {
        f"{prefix}_accuracy": float(accuracy_score(y_true, predicted)),
        f"{prefix}_log_loss": float(log_loss(y_true, probabilities, labels=classes)),
    }
    one_hot = np.zeros_like(probabilities, dtype=float)
    class_index = {value: index for index, value in enumerate(classes)}
    for row, value in enumerate(y_true):
        if int(value) in class_index:
            one_hot[row, class_index[int(value)]] = 1.0
    result[f"{prefix}_brier"] = float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1)))
    if len(classes) == 2 and len(set(int(value) for value in y_true)) == 2:
        positive = class_index.get(1, 1)
        result[f"{prefix}_roc_auc"] = float(roc_auc_score(y_true, probabilities[:, positive]))
    return result


def _fit(model_type: str, target: str, dataset: FeatureDataset, train_frame, params):
    kwargs = {
        "frame": train_frame,
        "y": train_frame[TARGET_COLUMNS[target]].astype(int),
        "target": target,
        "feature_columns": dataset.feature_columns,
        "categorical_columns": dataset.categorical_columns,
        "params": params,
    }
    if model_type == "xgboost":
        return fit_xgboost(**kwargs)
    if model_type == "catboost":
        return fit_catboost(**kwargs)
    raise ValueError(f"Unsupported model: {model_type}")


def train_models(
    *,
    config_path: str | None = None,
    models: Iterable[str] | None = None,
    targets: Iterable[str] | None = None,
    limit: int = 0,
) -> List[Dict[str, Any]]:
    config = load_config(config_path)
    configured_db = str(config.get("database_path") or "").strip()
    if configured_db:
        with database_path(configured_db):
            return _train_loaded(config, models=models, targets=targets, limit=limit)
    return _train_loaded(config, models=models, targets=targets, limit=limit)


def _train_loaded(
    config: Dict[str, Any],
    *,
    models: Iterable[str] | None,
    targets: Iterable[str] | None,
    limit: int,
) -> List[Dict[str, Any]]:
    create_database()
    catalog = DatabaseCatalog()
    dataset = build_feature_dataset(
        catalog,
        training=True,
        include_stacking=bool(config.get("include_stacking")),
    )
    if limit > 0:
        dataset.frame = dataset.frame.sort_values("kickoff_ts").tail(limit).copy()
    split_config = config.get("split") or {}
    split = temporal_split(
        dataset,
        train_ratio=float(split_config.get("train", 0.7)),
        validation_ratio=float(split_config.get("validation", 0.15)),
    )
    print(
        "[ML] dataset: "
        f"rows={len(dataset.frame)}, features={len(dataset.feature_columns)}, "
        f"train={len(split.train)}, validation={len(split.validation)}, test={len(split.test)}"
    )
    selected_models = list(models or config.get("models") or ["xgboost", "catboost"])
    selected_targets = list(targets or config.get("targets") or TARGET_COLUMNS)

    root = artifacts_dir(config)
    model_dir = root / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(tracking_uri(config))
    experiment_name = str(config.get("experiment_name") or "delux-football")
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        experiment_id = mlflow.create_experiment(
            experiment_name,
            artifact_location=artifact_root_uri(config),
        )
    else:
        experiment_id = experiment.experiment_id

    schema_hash = catalog.schema_hash()
    results: List[Dict[str, Any]] = []
    for model_type in selected_models:
        for target in selected_targets:
            if target not in TARGET_COLUMNS:
                raise ValueError(f"Unknown target: {target}")
            labels = set(int(value) for value in split.train[TARGET_COLUMNS[target]].dropna())
            expected = {0, 1, 2} if target == "1x2" else {0, 1}
            if labels != expected:
                raise ValueError(f"{model_type}/{target}: train labels {labels}, expected {expected}")
            with mlflow.start_run(experiment_id=experiment_id) as run:
                run_id = run.info.run_id
                bundle = _fit(
                    model_type,
                    target,
                    dataset,
                    split.train,
                    config.get(model_type) or {},
                )
                metrics: Dict[str, float] = {}
                for prefix, frame in (("validation", split.validation), ("test", split.test)):
                    probabilities = bundle.predict_proba(frame)
                    metrics.update(
                        _metrics(
                            frame[TARGET_COLUMNS[target]].astype(int).to_numpy(),
                            probabilities,
                            bundle.classes,
                            prefix,
                        )
                    )
                model_path = model_dir / f"{run_id}.joblib"
                joblib.dump(bundle, model_path)

                mlflow.set_tags({"model_type": model_type, "target": target, "schema_hash": schema_hash})
                mlflow.log_params(
                    {
                        "model_type": model_type,
                        "target": target,
                        "features": len(dataset.feature_columns),
                        "train_rows": len(split.train),
                        "validation_rows": len(split.validation),
                        "test_rows": len(split.test),
                        "train_from": str(split.train["match_date"].iloc[0]),
                        "train_to": str(split.train["match_date"].iloc[-1]),
                        "test_from": str(split.test["match_date"].iloc[0]),
                        "test_to": str(split.test["match_date"].iloc[-1]),
                        "include_stacking": bool(config.get("include_stacking")),
                    }
                )
                mlflow.log_metrics(metrics)
                mlflow.log_dict(config, "config.json")
                mlflow.log_dict(catalog.manifest(), "database_schema.json")
                mlflow.log_dict(
                    {
                        "labels": bundle.classes,
                        "validation": confusion_matrix(
                            split.validation[TARGET_COLUMNS[target]].astype(int),
                            bundle.predict(split.validation),
                            labels=bundle.classes,
                        ).tolist(),
                        "test": confusion_matrix(
                            split.test[TARGET_COLUMNS[target]].astype(int),
                            bundle.predict(split.test),
                            labels=bundle.classes,
                        ).tolist(),
                    },
                    "confusion_matrix.json",
                )
                mlflow.log_dict(
                    {
                        "feature_columns": dataset.feature_columns,
                        "categorical_columns": dataset.categorical_columns,
                    },
                    "feature_schema.json",
                )
                mlflow.log_artifact(str(model_path), artifact_path="models")

                record = {
                    "run_id": run_id,
                    "experiment": experiment_name,
                    "model_type": model_type,
                    "target": target,
                    "schema_hash": schema_hash,
                    "config_json": json.dumps(config, ensure_ascii=False),
                    "metrics_json": json.dumps(metrics, ensure_ascii=False),
                    "artifact_path": str(model_path),
                    "metrics": metrics,
                }
                upsert_ml_run(record)
                results.append(record)
                print(f"[+] {model_type}/{target}: run={run_id} test={metrics}")
    return results

