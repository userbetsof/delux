"""ML-каталог, признаки, temporal split и smoke-fit моделей."""

from __future__ import annotations

import sqlite3
import tempfile
import json
import joblib
from pathlib import Path
from unittest import TestCase

import pandas as pd

from src.ml.database import DatabaseCatalog
from src.ml.dataset import temporal_split
from src.ml.features import LEAKAGE_COLUMNS, build_feature_dataset


def _database(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE matches (
          match_id TEXT PRIMARY KEY, match_date TEXT, start_ts INTEGER,
          sport INTEGER, league_id INTEGER, home_team_id INTEGER, away_team_id INTEGER,
          match_status TEXT, score_home INTEGER, score_away INTEGER
        );
        CREATE TABLE odds (
          match_id TEXT, market_name TEXT, outcome TEXT, side TEXT,
          line_value REAL, odds_value REAL
        );
        CREATE TABLE match_snapshot (
          match_id TEXT, capacity INTEGER, weather_json TEXT, fetched_at TEXT
        );
        CREATE TABLE whoscored_preview (
          match_id TEXT, formation_home TEXT, formation_away TEXT,
          missing_json TEXT, lineups_json TEXT, fetched_at TEXT,
          score_home INTEGER, score_away INTEGER
        );
        INSERT INTO teams VALUES (1, 'Home'), (2, 'Away');
        INSERT INTO match_snapshot VALUES ('m0', 50000, '{}', '2026-01-02 12:00:00');
        INSERT INTO match_snapshot VALUES ('m1', 60000, '{}', '2026-01-01 12:00:00');
        INSERT INTO whoscored_preview VALUES (
          'm1', '4-4-2', '4-3-3', '{}', '{}', '2026-01-01 12:00:00', 9, 9
        );
        """
    )
    for index in range(12):
        conn.execute(
            """
            INSERT INTO matches VALUES (?, ?, ?, 1, 1, 1, 2, 'Завершен', ?, ?)
            """,
            (
                f"m{index}",
                f"2026.01.{index + 1:02d} 12:00",
                1767268800 + index * 86400,
                index % 4,
                (index + 1) % 3,
            ),
        )
        for outcome, odds in (("Home", 2.0), ("Draw", 3.2), ("Away", 3.8)):
            conn.execute(
                "INSERT INTO odds VALUES (?, '1X2', ?, NULL, NULL, ?)",
                (f"m{index}", outcome, odds),
            )
    conn.execute(
        "INSERT INTO matches VALUES ('future', '2026.02.01 12:00', 1769947200, 1, 1, 1, 2, 'Не начался', 0, 0)"
    )
    conn.commit()
    conn.close()


class TestMlDataset(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "ml.db"
        _database(self.path)
        self.catalog = DatabaseCatalog(str(self.path))

    def tearDown(self):
        self.tmp.cleanup()

    def test_catalog_has_full_read_only_schema(self):
        self.assertEqual(
            self.catalog.tables(),
            ["match_snapshot", "matches", "odds", "teams", "whoscored_preview"],
        )
        self.assertIn("score_home", [column["name"] for column in self.catalog.columns("matches")])
        self.assertEqual(self.catalog.count_rows()["matches"], 13)
        with self.assertRaises(ValueError):
            self.catalog.query("DELETE FROM matches")

    def test_feature_builder_separates_labels_and_leakage(self):
        dataset = build_feature_dataset(self.catalog, training=True)
        self.assertEqual(len(dataset.frame), 12)
        self.assertIn("target_1x2", dataset.frame)
        self.assertIn("target_over_2_5", dataset.frame)
        self.assertIn("odds_1", dataset.feature_columns)
        self.assertFalse(LEAKAGE_COLUMNS.intersection(dataset.feature_columns))
        by_id = dataset.frame.set_index("match_id")
        self.assertTrue(pd.isna(by_id.loc["m0", "capacity"]))
        self.assertEqual(by_id.loc["m1", "capacity"], 60000)
        self.assertNotIn("score_home", dataset.feature_columns)

    def test_future_dataset_has_no_labels(self):
        dataset = build_feature_dataset(self.catalog, training=False)
        self.assertEqual(dataset.frame["match_id"].tolist(), ["future"])
        self.assertNotIn("target_1x2", dataset.frame)

    def test_temporal_split_never_shuffles(self):
        dataset = build_feature_dataset(self.catalog, training=True)
        split = temporal_split(dataset, train_ratio=0.5, validation_ratio=0.25)
        self.assertLess(split.train["kickoff_ts"].max(), split.validation["kickoff_ts"].min())
        self.assertLess(split.validation["kickoff_ts"].max(), split.test["kickoff_ts"].min())

    def test_prediction_probability_serialization(self):
        from src.ml.predict import serialize_probabilities

        value = json.loads(serialize_probabilities("1x2", [0, 1, 2], [0.2, 0.5, 0.3]))
        self.assertEqual(value, {"X": 0.2, "П1": 0.5, "П2": 0.3})


class TestMlModels(TestCase):
    @classmethod
    def setUpClass(cls):
        rows = 30
        cls.frame = pd.DataFrame(
            {
                "numeric": [float(i % 7) for i in range(rows)],
                "league_id": [str(i % 3) for i in range(rows)],
            }
        )
        cls.y_binary = pd.Series([i % 2 for i in range(rows)])

    def test_xgboost_smoke_fit(self):
        from src.ml.models.xgboost_model import fit_xgboost

        bundle = fit_xgboost(
            self.frame,
            self.y_binary,
            target="over_2_5",
            feature_columns=["numeric", "league_id"],
            categorical_columns=["league_id"],
            params={"n_estimators": 3, "max_depth": 2, "random_state": 1},
        )
        self.assertEqual(bundle.predict_proba(self.frame[:2]).shape, (2, 2))

    def test_catboost_smoke_fit(self):
        from src.ml.models.catboost_model import fit_catboost

        bundle = fit_catboost(
            self.frame,
            self.y_binary,
            target="over_2_5",
            feature_columns=["numeric", "league_id"],
            categorical_columns=["league_id"],
            params={"iterations": 3, "depth": 2, "verbose": False, "random_seed": 1},
        )
        self.assertEqual(bundle.predict_proba(self.frame[:2]).shape, (2, 2))


class TestMlStorage(TestCase):
    def test_migration_and_prediction_upsert(self):
        from db import (
            create_database,
            database_path,
            get_db_connection,
            upsert_ml_prediction,
            upsert_ml_run,
        )

        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "migration.db")
            with database_path(path):
                create_database()
                with get_db_connection() as conn:
                    conn.execute(
                        "INSERT INTO matches (match_id, match_date, sport) VALUES ('future1', '2026.01.01 12:00', 1)"
                    )
                    conn.commit()
                upsert_ml_run(
                    {
                        "run_id": "run1",
                        "experiment": "test",
                        "model_type": "xgboost",
                        "target": "1x2",
                        "schema_hash": "abc",
                        "config_json": "{}",
                        "metrics_json": "{}",
                        "artifact_path": "model.joblib",
                    }
                )
                prediction = {
                    "match_id": "future1",
                    "run_id": "run1",
                    "model_type": "xgboost",
                    "target": "1x2",
                    "prediction": "П1",
                    "probability_json": '{"П1": 0.6}',
                }
                upsert_ml_prediction(prediction)
                prediction["prediction"] = "X"
                upsert_ml_prediction(prediction)
                with get_db_connection() as conn:
                    rows = conn.execute("SELECT * FROM ml_predictions").fetchall()
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0]["prediction"], "X")

    def test_future_match_inference_writes_prediction(self):
        from sklearn.dummy import DummyClassifier

        from db import create_database, database_path, get_db_connection, upsert_ml_run
        from src.ml.models.common import ModelBundle
        from src.ml.predict import predict_matches

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db_path = root / "predict.db"
            model_path = root / "model.joblib"
            config_path = root / "config.json"
            estimator = DummyClassifier(strategy="prior").fit(
                pd.DataFrame({"kickoff_hour": [10, 12, 14]}),
                [0, 1, 2],
            )
            joblib.dump(
                ModelBundle(
                    model_type="xgboost",
                    target="1x2",
                    feature_columns=["kickoff_hour"],
                    categorical_columns=[],
                    model=estimator,
                    classes=[0, 1, 2],
                ),
                model_path,
            )
            config_path.write_text(
                json.dumps(
                    {
                        "database_path": str(db_path),
                        "include_stacking": False,
                        "models": ["xgboost"],
                        "targets": ["1x2"],
                    }
                ),
                encoding="utf-8",
            )
            with database_path(str(db_path)):
                create_database()
                with get_db_connection() as conn:
                    conn.execute("INSERT INTO teams (name) VALUES ('Home'), ('Away')")
                    teams = conn.execute("SELECT id, name FROM teams").fetchall()
                    ids = {row["name"]: row["id"] for row in teams}
                    conn.execute(
                        """
                        INSERT INTO matches (
                          match_id, match_date, start_ts, home_team_id, away_team_id, sport
                        ) VALUES ('future1', '2026.09.11 12:00', 1789128000, ?, ?, 1)
                        """,
                        (ids["Home"], ids["Away"]),
                    )
                    conn.commit()
                upsert_ml_run(
                    {
                        "run_id": "run-predict",
                        "experiment": "test",
                        "model_type": "xgboost",
                        "target": "1x2",
                        "schema_hash": "abc",
                        "config_json": "{}",
                        "metrics_json": "{}",
                        "artifact_path": str(model_path),
                    }
                )

            records = predict_matches(config_path=str(config_path), match_id="future1")
            self.assertEqual(len(records), 1)
            with database_path(str(db_path)):
                with get_db_connection() as conn:
                    saved = conn.execute("SELECT * FROM ml_predictions").fetchall()
                    self.assertEqual(len(saved), 1)
                    self.assertEqual(saved[0]["match_id"], "future1")

