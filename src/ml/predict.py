from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import joblib

from db import create_database, database_path, get_db_connection, upsert_ml_prediction
from src.ml.config import load_config, tracking_uri
from src.ml.database import DatabaseCatalog
from src.ml.features import build_feature_dataset

CLASS_NAMES = {
    "1x2": {0: "X", 1: "П1", 2: "П2"},
    "over_2_5": {0: "ТМ 2.5", 1: "ТБ 2.5"},
}


def serialize_probabilities(target: str, classes, probabilities) -> str:
    names = CLASS_NAMES[target]
    return json.dumps(
        {
            names[int(class_id)]: float(probabilities[index])
            for index, class_id in enumerate(classes)
        },
        ensure_ascii=False,
    )


def _runs(run_id: str = "", model_type: str = "", sport: int = 0) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        if run_id:
            rows = conn.execute("SELECT * FROM ml_runs WHERE run_id = ?", (run_id,)).fetchall()
        else:
            condition = ""
            params: list = []
            
            if model_type:
                condition += " AND r.model_type = ?"
                params.append(model_type)
            if sport > 0:
                condition += " AND r.sport = ?"
                params.append(sport)
            
            rows = conn.execute(
                f"""
                SELECT r.* FROM ml_runs r
                WHERE r.rowid = (
                    SELECT MAX(x.rowid) FROM ml_runs x
                    WHERE x.model_type=r.model_type AND x.target=r.target AND x.sport=r.sport
                )
                {condition}
                """,
                tuple(params),
            ).fetchall()
    return [dict(row) for row in rows]


def predict_matches(
    *,
    config_path: str | None = None,
    run_id: str = "",
    model_type: str = "",
    match_id: str = "",
) -> List[Dict[str, Any]]:
    config = load_config(config_path)
    configured_db = str(config.get("database_path") or "").strip()
    if configured_db:
        with database_path(configured_db):
            return _predict_loaded(
                config,
                run_id=run_id,
                model_type=model_type,
                match_id=match_id,
            )
    return _predict_loaded(config, run_id=run_id, model_type=model_type, match_id=match_id)


def _predict_loaded(
    config: Dict[str, Any],
    *,
    run_id: str,
    model_type: str,
    match_id: str,
) -> List[Dict[str, Any]]:
    create_database()
    dataset = build_feature_dataset(
        DatabaseCatalog(),
        training=False,
        include_stacking=bool(config.get("include_stacking")),
    )
    frame = dataset.frame
    if match_id:
        frame = frame[frame["match_id"] == match_id].copy()
    if frame.empty:
        print("[-] Нет будущих матчей для ML-инференса")
        return []

    records: List[Dict[str, Any]] = []
    for run in _runs(run_id, model_type):
        path = Path(str(run.get("artifact_path") or ""))
        if not path.exists():
            import mlflow

            mlflow.set_tracking_uri(tracking_uri(config))
            path = Path(
                mlflow.artifacts.download_artifacts(
                    run_id=str(run["run_id"]),
                    artifact_path=f"models/{run['run_id']}.joblib",
                )
            )
        bundle = joblib.load(path)
        probabilities = bundle.predict_proba(frame)
        predictions = bundle.predict(frame)
        names = CLASS_NAMES[bundle.target]
        for position, (_, row) in enumerate(frame.iterrows()):
            record = {
                "match_id": str(row["match_id"]),
                "run_id": str(run["run_id"]),
                "model_type": bundle.model_type,
                "target": bundle.target,
                "prediction": names[int(predictions[position])],
                "probability_json": serialize_probabilities(
                    bundle.target,
                    bundle.classes,
                    probabilities[position],
                ),
            }
            upsert_ml_prediction(record)
            records.append(record)
        print(f"[+] {bundle.model_type}/{bundle.target}: прогнозов {len(frame)}")
    return records

