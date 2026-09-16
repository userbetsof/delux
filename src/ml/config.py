from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "ml" / "default.json"


def load_config(path: str | None = None) -> Dict[str, Any]:
    config_path = Path(path or os.environ.get("ML_CONFIG") or DEFAULT_CONFIG)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    data = json.loads(config_path.read_text(encoding="utf-8"))
    data["_config_path"] = str(config_path.resolve())
    data["_root"] = str(ROOT)
    return data


def artifacts_dir(config: Dict[str, Any] | None = None) -> Path:
    raw = (
        os.environ.get("ML_ARTIFACTS_DIR")
        or (config or {}).get("artifacts_dir")
        or "artifacts/ml"
    )
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def tracking_uri(config: Dict[str, Any] | None = None) -> str:
    explicit = (
        os.environ.get("MLFLOW_TRACKING_URI")
        or (config or {}).get("mlflow_tracking_uri")
        or ""
    ).strip()
    if explicit:
        return explicit
    db_path = artifacts_dir(config) / "mlflow.db"
    return f"sqlite:///{db_path.as_posix()}"


def artifact_root_uri(config: Dict[str, Any] | None = None) -> str:
    return (artifacts_dir(config) / "mlartifacts").as_uri()

