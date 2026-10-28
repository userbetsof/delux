import sys
sys.path.insert(0, "C:/papki/work/bets/delux")

from src.ml.features import build_feature_dataset
from src.ml.database import DatabaseCatalog

dataset = build_feature_dataset(DatabaseCatalog(), training=True, include_stacking=False)

print(f"Rows: {len(dataset.frame)}")
print(f"Sports: {dataset.frame['sport'].unique()}")
print(f"Sport types: {[type(s).__name__ for s in dataset.frame['sport'].unique()]}")
