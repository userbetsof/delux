"""Исследование: XGBoost с ОДНИМ признаком — форма команды за последние 10 матчей.

Признак (единственный):
    form10_diff = ppg(хозяева, последние 10 матчей) - ppg(гости, последние 10 матчей)
    ppg = очки за матч, победа 3 / ничья 1 / поражение 0, усреднение по последним <=10 матчам.

Цель: 1x2 -> 0 = ничья, 1 = победа хозяев, 2 = победа гостей (кодировка как в src/ml/features.py).

Гарантия отсутствия утечки: история команды строится только по матчам строго раньше текущего;
матчи с одинаковой датой не видят друг друга.

Сравнения: XGBoost / правило знака формы / мажоритарный класс / линия букмекера (кэ-оды, медиана).
"""
from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, log_loss
from xgboost import XGBClassifier

ROOT = Path(r"C:\papki\work\bets\delux")
DB = ROOT / "matches.db"
OUT = ROOT / "research" / "form10_results.json"

WINDOW = 10
SEED = 42
BOOTSTRAP = 2000
SPORT_NAMES = {1: "футбол", 4: "хоккей", 6: "бейсбол"}

XGB_PARAMS = dict(
    n_estimators=300,
    max_depth=3,
    learning_rate=0.05,
    subsample=0.9,
    colsample_bytree=1.0,
    reg_lambda=1.0,
    min_child_weight=5,
    objective="multi:softprob",
    eval_metric="mlogloss",
    tree_method="hist",
    random_state=SEED,
    n_jobs=-1,
)
rng = np.random.default_rng(SEED)


# ----------------------------------------------------------------------------- данные
def load_matches() -> pd.DataFrame:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    frame = pd.read_sql_query(
        """
        SELECT m.match_id, m.match_date, m.sport, m.league_id,
               m.home_team_id, m.away_team_id, m.score_home, m.score_away,
               ht.name AS home_name, at.name AS away_name
        FROM matches m
        LEFT JOIN teams ht ON ht.id = m.home_team_id
        LEFT JOIN teams at ON at.id = m.away_team_id
        WHERE m.match_status = 'Завершен'
          AND m.score_home IS NOT NULL AND m.score_away IS NOT NULL
          AND m.match_date IS NOT NULL AND TRIM(m.match_date) != ''
        """,
        con,
    )
    con.close()
    frame["match_date"] = frame["match_date"].astype(str).str.strip()
    frame["sport"] = pd.to_numeric(frame["sport"], errors="coerce").fillna(-1).astype(int)
    return frame


def load_odds() -> pd.DataFrame:
    """Кэ-оды 1X2. Медиана по дубликатам-снапшотам (max() систематически завышает кэф)."""
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    frame = pd.read_sql_query(
        """
        SELECT match_id, market_name, odds_value
        FROM odds
        WHERE market_name IN ('1X2_1','1X2_X','1X2_2')
          AND odds_value IS NOT NULL AND odds_value > 1.0
        """,
        con,
    )
    con.close()
    pivot = frame.pivot_table(
        index="match_id", columns="market_name", values="odds_value", aggfunc="median"
    )
    pivot = pivot.rename(columns={"1X2_1": "odds_1", "1X2_X": "odds_x", "1X2_2": "odds_2"})
    for column in ("odds_1", "odds_x", "odds_2"):
        if column not in pivot:
            pivot[column] = np.nan
    return pivot[["odds_1", "odds_x", "odds_2"]].reset_index()


# ------------------------------------------------------------------- признак формы
def _match_points(score_home: float, score_away: float) -> tuple[int, int]:
    if score_home > score_away:
        return 3, 0
    if score_home < score_away:
        return 0, 3
    return 1, 1


def build_form_features(frame: pd.DataFrame) -> pd.DataFrame:
    ordered = frame.sort_values(["match_date", "match_id"]).copy()
    history: dict[tuple[int, int], list[int]] = defaultdict(list)
    records: list[dict] = []

    for date, group in ordered.groupby("match_date", sort=True):
        pending: list[dict] = []
        for row in group.itertuples(index=False):
            home_pts = history[(row.sport, row.home_team_id)][-WINDOW:]
            away_pts = history[(row.sport, row.away_team_id)][-WINDOW:]
            n_home, n_away = len(home_pts), len(away_pts)
            ppg_home = float(np.mean(home_pts)) if n_home else math.nan
            ppg_away = float(np.mean(away_pts)) if n_away else math.nan

            if row.score_home > row.score_away:
                target = 1
            elif row.score_home < row.score_away:
                target = 2
            else:
                target = 0

            pending.append({
                "match_id": row.match_id, "match_date": date, "sport": row.sport,
                "league_id": row.league_id,
                "home_team_id": row.home_team_id, "away_team_id": row.away_team_id,
                "home_name": row.home_name, "away_name": row.away_name,
                "score_home": row.score_home, "score_away": row.score_away,
                "target": target,
                "form10_ppg_home": ppg_home, "form10_ppg_away": ppg_away,
                "form10_diff": ppg_home - ppg_away,
                "n_home": n_home, "n_away": n_away,
            })

        for row in group.itertuples(index=False):
            home_points, away_points = _match_points(row.score_home, row.score_away)
            history[(row.sport, row.home_team_id)].append(home_points)
            history[(row.sport, row.away_team_id)].append(away_points)

        records.extend(pending)

    return pd.DataFrame(records)


# ------------------------------------------------------------------------ метрики
CLASSES = [0, 1, 2]


def metrics(y_true: np.ndarray, proba: np.ndarray) -> dict:
    predicted = np.asarray(CLASSES)[proba.argmax(axis=1)]
    one_hot = np.zeros_like(proba, dtype=float)
    for i, value in enumerate(y_true):
        one_hot[i, CLASSES.index(int(value))] = 1.0
    return {
        "n": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, predicted)),
        "log_loss": float(log_loss(y_true, proba, labels=CLASSES)),
        "brier": float(np.mean(np.sum((proba - one_hot) ** 2, axis=1))),
        "confusion": confusion_matrix(y_true, predicted, labels=CLASSES).tolist(),
    }


def bootstrap_ci(values: np.ndarray, *, statistic=np.mean, n: int = BOOTSTRAP) -> dict:
    if len(values) == 0:
        return {"point": float("nan"), "lo": float("nan"), "hi": float("nan")}
    idx = rng.integers(0, len(values), size=(n, len(values)))
    samples = statistic(values[idx], axis=1)
    return {
        "point": float(statistic(values)),
        "lo": float(np.percentile(samples, 5)),
        "hi": float(np.percentile(samples, 95)),
    }


def temporal_split(frame: pd.DataFrame, train=0.7, validation=0.15) -> tuple:
    ordered = frame.sort_values(["match_date", "match_id"]).reset_index(drop=True)
    size = len(ordered)
    train_end = max(1, int(size * train))
    val_end = min(max(train_end + 1, int(size * (train + validation))), size - 1)
    return ordered.iloc[:train_end], ordered.iloc[train_end:val_end], ordered.iloc[val_end:]


def market_probs(frame: pd.DataFrame) -> np.ndarray:
    """Вероятности букмекера в порядке классов [ничья, хозяин, гость] = [0, 1, 2]."""
    odds = frame[["odds_x", "odds_1", "odds_2"]].to_numpy(dtype=float)
    inverse = 1.0 / odds
    return inverse / inverse.sum(axis=1, keepdims=True)


def add_picks(frame: pd.DataFrame, proba: np.ndarray) -> pd.DataFrame:
    """Добавляет выбор модели и кэф на этот выбор. Ставка возможна, только если кэф есть."""
    out = frame.copy()
    out["pred"] = np.asarray(CLASSES)[proba.argmax(axis=1)]
    out["p_max"] = proba.max(axis=1)
    out["p_home"] = proba[:, 1]
    out["p_draw"] = proba[:, 0]
    out["p_away"] = proba[:, 2]
    odds_map = {0: "odds_x", 1: "odds_1", 2: "odds_2"}
    out["odds_pick"] = [
        out.at[i, odds_map[p]] if pd.notna(out.at[i, odds_map[p]]) else np.nan
        for i, p in zip(out.index, out["pred"])
    ]
    out["won"] = out["pred"] == out["target"]
    return out


def roi_report(picks: pd.DataFrame, threshold: float, value_only: bool = False) -> dict:
    if picks.empty:
        return {"bets": 0, "profit": 0.0, "roi": 0.0, "hit_rate": 0.0,
                "roi_lo": float("nan"), "roi_hi": float("nan")}
    bet = picks.dropna(subset=["odds_pick"]).copy()
    bet = bet[bet["p_max"] >= threshold]
    if value_only:
        implied = 1.0 / bet["odds_pick"]
        bet = bet[bet["p_max"] > implied]
    if bet.empty:
        return {"bets": 0, "profit": 0.0, "roi": 0.0, "hit_rate": 0.0,
                "roi_lo": float("nan"), "roi_hi": float("nan")}
    profit = np.where(bet["won"], bet["odds_pick"] - 1.0, -1.0)
    ci = bootstrap_ci(profit)
    return {
        "bets": int(len(bet)),
        "profit": float(profit.sum()),
        "roi": float(profit.mean()),
        "roi_lo": ci["lo"],
        "roi_hi": ci["hi"],
        "hit_rate": float(bet["won"].mean()),
        "avg_odds": float(bet["odds_pick"].mean()),
    }


# -------------------------------------------------------------------- эксперимент
def run_sport(data: pd.DataFrame, sport: int, variant: str) -> dict:
    subset = data[data["sport"] == sport].copy()
    if variant == "strict":
        subset = subset[(subset["n_home"] >= WINDOW) & (subset["n_away"] >= WINDOW)]
    else:
        subset = subset[(subset["n_home"] >= 1) & (subset["n_away"] >= 1)]
    subset = subset.dropna(subset=["form10_diff"]).copy()

    report: dict = {
        "sport": sport, "sport_name": SPORT_NAMES.get(sport, str(sport)),
        "variant": variant, "rows": int(len(subset)),
    }
    if len(subset) < 100:
        report["error"] = f"слишком мало строк ({len(subset)})"
        return report

    train, validation, test = temporal_split(subset)
    report["split"] = {
        "train": len(train), "validation": len(validation), "test": len(test),
        "train_from": str(train["match_date"].iloc[0]), "train_to": str(train["match_date"].iloc[-1]),
        "test_from": str(test["match_date"].iloc[0]), "test_to": str(test["match_date"].iloc[-1]),
    }
    report["class_balance"] = {
        "train": {int(k): int(v) for k, v in train["target"].value_counts().items()},
        "validation": {int(k): int(v) for k, v in validation["target"].value_counts().items()},
        "test": {int(k): int(v) for k, v in test["target"].value_counts().items()},
    }

    feature = "form10_diff"
    model = XGBClassifier(**XGB_PARAMS)
    model.fit(train[[feature]], train["target"].astype(int))
    report["classes"] = [int(c) for c in model.classes_]

    report["metrics"] = {
        "validation": metrics(validation["target"].to_numpy(), model.predict_proba(validation[[feature]])),
        "test": metrics(test["target"].to_numpy(), model.predict_proba(test[[feature]])),
    }

    # --- baselines ---
    majority = int(train["target"].mode().iloc[0])
    majority_proba = np.zeros((len(test), len(CLASSES)))
    majority_proba[:, CLASSES.index(majority)] = 1.0
    report["baseline_majority"] = {"class": majority, "test": metrics(test["target"].to_numpy(), majority_proba)}

    sign_pred = np.where(test["form10_diff"] > 0, 1, np.where(test["form10_diff"] < 0, 2, 0))
    report["baseline_sign_rule"] = {
        "test_accuracy": float(accuracy_score(test["target"], sign_pred)),
        "confusion": confusion_matrix(test["target"], sign_pred, labels=CLASSES).tolist(),
    }

    # --- линия букмекера (только там, где есть полный набор 1X2) ---
    full_market = test[["odds_x", "odds_1", "odds_2"]].notna().all(axis=1)
    report["market_coverage"] = float(full_market.mean())
    if full_market.sum() > 20:
        market_test = test[full_market]
        report["baseline_market"] = metrics(market_test["target"].to_numpy(), market_probs(market_test))

    # --- тест: XGBoost ---
    test_proba = model.predict_proba(test[[feature]])
    picks = add_picks(test, test_proba)
    ci = bootstrap_ci((picks["pred"] == picks["target"]).to_numpy().astype(float))
    report["test_accuracy_ci"] = ci

    report["roi_test"] = {
        str(t): roi_report(picks, t) for t in (0.0, 0.45, 0.50, 0.55, 0.60)
    }
    report["roi_test_value"] = {str(t): roi_report(picks, t, value_only=True) for t in (0.0, 0.45, 0.50)}

    # --- сколько выборов приходится на ничью (нельзя поставить при отсутствии рынка X) ---
    report["pick_distribution"] = {int(k): int(v) for k, v in picks["pred"].value_counts().items()}

    # --- правило знака формы как ставка (сравнение с XGBoost) ---
    sign_proba = np.zeros((len(test), len(CLASSES)))
    sign_proba[np.arange(len(test)), sign_pred] = 1.0
    sign_picks = add_picks(test, sign_proba + 1e-9)
    report["roi_sign_rule"] = {str(t): roi_report(sign_picks, t) for t in (0.0, 0.50)}

    # --- интерпретация ---
    trees = model.get_booster().trees_to_dataframe()
    report["split_thresholds"] = sorted({
        round(float(v), 4) for v in trees["Split"].dropna().unique()
        if isinstance(v, (int, float, np.floating))
    })[:40]
    report["feature_importance"] = {feature: float(model.feature_importances_[0])}

    # --- model-free: исходы по корзинам формы ---
    bins = [-np.inf, -1.5, -1.0, -0.5, -0.2, 0.2, 0.5, 1.0, 1.5, np.inf]
    bucket = pd.cut(subset["form10_diff"], bins=bins)
    table = (
        subset.groupby(bucket, observed=True)["target"]
        .agg(n="size",
             home_win=lambda s: float((s == 1).mean()),
             draw=lambda s: float((s == 0).mean()),
             away_win=lambda s: float((s == 2).mean()))
        .reset_index()
    )
    table["form10_diff"] = table["form10_diff"].astype(str)
    report["outcome_by_form_bucket"] = table.to_dict(orient="records")

    # --- model-free: сила сигнала (корреляция формы с исходом) ---
    signed = np.where(subset["target"] == 1, 1.0, np.where(subset["target"] == 2, -1.0, 0.0))
    report["corr_form_vs_result"] = float(np.corrcoef(subset["form10_diff"], signed)[0, 1])
    return report


def main() -> int:
    matches = load_matches()
    odds = load_odds()
    print(f"завершённых матчей с датой: {len(matches)}; матчей с кэ-одами 1X2: {len(odds)}")

    features = build_form_features(matches).merge(odds, on="match_id", how="left")

    print("\nпокрытие формы по видам спорта:")
    for sport in sorted(features["sport"].unique()):
        block = features[features["sport"] == sport]
        both1 = int(((block["n_home"] >= 1) & (block["n_away"] >= 1)).sum())
        both10 = int(((block["n_home"] >= WINDOW) & (block["n_away"] >= WINDOW)).sum())
        print(f"  sport={sport} ({SPORT_NAMES.get(sport, '?')}): n={len(block)} обе>=1: {both1} обе>=10: {both10}")

    reports = []
    for sport in (6, 1):
        for variant in ("strict", "graceful"):
            reports.append(run_sport(features, sport, variant))

    payload = {
        "config": {
            "window": WINDOW,
            "points": "победа 3 / ничья 1 / поражение 0",
            "feature": "form10_diff = ppg(хозяева, последние 10) - ppg(гости, последние 10)",
            "target": "0=ничья, 1=победа хозяев, 2=победа гостей",
            "split": "temporal 70/15/15",
            "xgb_params": XGB_PARAMS, "seed": SEED,
            "odds": "медиана по снапшотам (1X2_1/1X2_X/1X2_2)",
            "bootstrap": BOOTSTRAP,
        },
        "reference_full_feature_xgboost_1x2": {
            "sport=1": {"test_accuracy": 0.4859, "test_log_loss": 0.9795},
            "sport=6": {"test_accuracy": 0.5545, "test_log_loss": 0.7827},
            "source": "matches.db / ml_runs (полный набор признаков из src/ml/features.py)",
        },
        "database": str(DB),
        "reports": reports,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nрезультаты сохранены: {OUT}")

    for rep in reports:
        print("\n" + "=" * 78)
        print(f"SPORT {rep['sport']} ({rep['sport_name']}) | вариант: {rep['variant']} | строк: {rep.get('rows')}")
        print("=" * 78)
        if "error" in rep:
            print("   ", rep["error"])
            continue
        print(f"  split: {rep['split']}")
        print(f"  классы test: {rep['class_balance']['test']}")
        for name in ("test", "validation"):
            m = rep["metrics"][name]
            print(f"  XGB  [{name:10s}] n={m['n']:4d} acc={m['accuracy']:.4f} logloss={m['log_loss']:.4f} brier={m['brier']:.4f}")
            print(f"        confusion={m['confusion']}")
        ci = rep["test_accuracy_ci"]
        print(f"  точность XGB на тесте: {ci['point']:.3f} (90% ДИ {ci['lo']:.3f}..{ci['hi']:.3f})")
        bm = rep["baseline_majority"]
        print(f"  мажоритарный класс {bm['class']}: acc={bm['test']['accuracy']:.4f} logloss={bm['test']['log_loss']:.4f}")
        print(f"  правило знака формы: acc={rep['baseline_sign_rule']['test_accuracy']:.4f}")
        if "baseline_market" in rep:
            mk = rep["baseline_market"]
            print(f"  БУКМЕКЕР (n={mk['n']}, покрытие={rep['market_coverage']:.1%}): "
                  f"acc={mk['accuracy']:.4f} logloss={mk['log_loss']:.4f} brier={mk['brier']:.4f}")
        print(f"  corr(форма, результат) = {rep['corr_form_vs_result']:+.4f}")
        print("  ROI XGBoost на тесте:")
        for thr, r in rep["roi_test"].items():
            print(f"    порог {thr}: ставок={r['bets']:4d} профит={r['profit']:+8.2f} "
                  f"ROI={r['roi']:+7.2%} (90% ДИ {r['roi_lo']:+.2%}..{r['roi_hi']:+.2%}) "
                  f"попадание={r['hit_rate']:.1%} ср.кэф={r.get('avg_odds', float('nan')):.2f}")
        print("  ROI правило знака формы:")
        for thr, r in rep["roi_sign_rule"].items():
            print(f"    порог {thr}: ставок={r['bets']:4d} ROI={r['roi']:+7.2%}")
        print(f"  пороги разбиения деревьев: {rep['split_thresholds'][:20]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
