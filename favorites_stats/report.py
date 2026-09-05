"""Формирование и сохранение отчёта favorites_stats."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from favorites_stats.backtest import run_backtest
from favorites_stats.injuries import build_injuries_report
from favorites_stats.repository import load_finished_matches

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "favorites_stats_report.json"


def build_report(
    *,
    db_path: Optional[str] = None,
    favorite_leagues_only: bool = False,
    odds_min: float = 1.1,
    odds_max: float = 4.0,
    odds_step: float = 0.1,
    fetch_injuries: bool = False,
    fetch_injuries_limit: int = 50,
) -> Dict[str, Any]:
    matches = load_finished_matches(db_path, favorite_leagues_only=favorite_leagues_only)
    backtest = run_backtest(
        matches,
        odds_min=odds_min,
        odds_max=odds_max,
        odds_step=odds_step,
    )
    injuries = build_injuries_report(
        db_path,
        fetch=fetch_injuries,
        fetch_limit=fetch_injuries_limit,
        finished_matches=matches,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "module": "favorites_stats",
        "description": (
            "Статистика ставок на фаворитов: оптимальные кф победы и форы по видам спорта. "
            "Сигналы не генерируются."
        ),
        "params": {
            "favorite_leagues_only": favorite_leagues_only,
            "odds_grid": {"min": odds_min, "max": odds_max, "step": odds_step},
            "fetch_injuries": fetch_injuries,
            "fetch_injuries_limit": fetch_injuries_limit,
        },
        "backtest": backtest,
        "injuries": injuries,
    }


def save_report(report: Dict[str, Any], out_path: Optional[Path] = None) -> Path:
    path = out_path or DEFAULT_OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def print_summary(report: Dict[str, Any]) -> None:
    bt = report.get("backtest", {})
    totals = bt.get("totals", {})
    print(f"Матчей в выборке: {totals.get('matches', 0)}")
    print(f"Видов спорта: {totals.get('sports', 0)}")
    win = totals.get("win_bets", {})
    hcap = totals.get("handicap_bets", {})
    print(
        f"Победа фаворита: {win.get('bets', 0)} ставок, "
        f"profit={win.get('profit', 0)}, ROI={win.get('roi_pct')}%"
    )
    print(
        f"Фора фаворита: {hcap.get('bets', 0)} ставок, "
        f"profit={hcap.get('profit', 0)}, ROI={hcap.get('roi_pct')}%"
    )
    print()
    for sport in bt.get("by_sport", []):
        print(f"=== {sport['sport_name']} (id={sport['sport_id']}) ===")
        print(f"  Матчей: {sport['total_matches']}, с фаворитом: {sport['with_favorite']}")
        ow = sport.get("optimal_win_odds_bucket")
        oh = sport.get("optimal_handicap_odds_bucket")
        rw = sport.get("optimal_win_odds_range")
        rh = sport.get("optimal_handicap_odds_range")
        if ow:
            print(
                f"  Лучший кф победы (бакет): {ow['odds_bucket']} — "
                f"profit={ow['profit']}, ROI={ow['roi_pct']}% ({ow['bets']} ставок)"
            )
        if rw:
            print(
                f"  Лучший диапазон кф победы: {rw['odds_min']}–{rw['odds_max']} — "
                f"profit={rw['profit']}, ROI={rw['roi_pct']}%"
            )
        if oh:
            print(
                f"  Лучший кф форы (бакет): {oh['odds_bucket']} — "
                f"profit={oh['profit']}, ROI={oh['roi_pct']}% ({oh['bets']} ставок)"
            )
        if rh:
            print(
                f"  Лучший диапазон кф форы: {rh['odds_min']}–{rh['odds_max']} — "
                f"profit={rh['profit']}, ROI={rh['roi_pct']}%"
            )
        print()

    inj = report.get("injuries", {})
    print(f"Травмы: [{inj.get('status')}] {inj.get('message', '')}")
    if inj.get("available"):
        print(f"  Матчей с данными: {inj.get('matches_with_data', 0)}")
        print(f"  С подтверждёнными травмами: {inj.get('matches_with_confirmed_injuries', 0)}")
        impact = inj.get("favorite_win_impact") or {}
        for key, label in (
            ("favorite_has_injury", "Фаворит с травмами"),
            ("underdog_has_injury", "Андердог с травмами"),
            ("favorite_no_injury", "Без травм"),
            ("no_lineup_data", "Нет данных о составе"),
        ):
            row = impact.get(key) or {}
            if row.get("bets"):
                print(
                    f"  {label}: {row['bets']} матчей, winrate={row.get('winrate_pct')}%, "
                    f"ROI={row.get('roi_pct')}%"
                )
    fetch = inj.get("fetch")
    if fetch:
        print(
            f"  Загрузка API: ok={fetch.get('fetched_ok', 0)}/{fetch.get('to_fetch', 0)}, "
            f"строк={fetch.get('rows_saved', 0)}"
        )
