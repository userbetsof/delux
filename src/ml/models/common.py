from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np
import pandas as pd


@dataclass
class ModelBundle:
    model_type: str
    target: str
    feature_columns: List[str]
    categorical_columns: List[str]
    model: Any
    numeric_medians: Dict[str, float] = field(default_factory=dict)
    classes: List[int] = field(default_factory=list)

    def prepare_catboost(self, frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.reindex(columns=self.feature_columns).copy()
        for column in self.categorical_columns:
            result[column] = result[column].fillna("__missing__").astype(str)
        for column in self.feature_columns:
            if column in self.categorical_columns:
                continue
            result[column] = pd.to_numeric(result[column], errors="coerce").fillna(
                self.numeric_medians.get(column, 0.0)
            )
        return result

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        data = (
            self.prepare_catboost(frame)
            if self.model_type == "catboost"
            else frame.reindex(columns=self.feature_columns)
        )
        return np.asarray(self.model.predict_proba(data))

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        probabilities = self.predict_proba(frame)
        indexes = probabilities.argmax(axis=1)
        classes = np.asarray(self.classes or list(range(probabilities.shape[1])))
        return classes[indexes]

