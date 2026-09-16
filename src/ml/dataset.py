from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.ml.features import FeatureDataset


@dataclass
class TemporalSplit:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame


def temporal_split(
    dataset: FeatureDataset,
    *,
    train_ratio: float = 0.7,
    validation_ratio: float = 0.15,
) -> TemporalSplit:
    frame = dataset.frame.dropna(subset=["kickoff_ts"]).sort_values(
        ["kickoff_ts", "match_id"]
    )
    size = len(frame)
    if size < 10:
        raise ValueError(f"At least 10 labeled matches required, got {size}")
    train_end = max(1, int(size * train_ratio))
    validation_end = max(train_end + 1, int(size * (train_ratio + validation_ratio)))
    validation_end = min(validation_end, size - 1)
    return TemporalSplit(
        train=frame.iloc[:train_end].copy(),
        validation=frame.iloc[train_end:validation_end].copy(),
        test=frame.iloc[validation_end:].copy(),
    )

