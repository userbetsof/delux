"""Бэктест прибыли по кф победы фаворита и форы."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from favorites_stats.repository import FinishedMatch
from favorites_stats.settlement import (
    favorite_handicap_lines,
    identify_favorite,
    profit_for_result,
    select_handicap_bet_line,
    settle_handicap,
    settle_win,
)
from favorites_stats.sports import sport_label


@dataclass
class BucketStats:
    bets: int = 0
    wins: int = 0
    pushes: int = 0
    profit: float = 0.0

    def to_dict(self) -> dict:
        losses = self.bets - self.wins
        return {
            "bets": self.bets,
            "wins": self.wins,
            "losses": losses,
            "pushes": self.pushes,
            "profit": round(self.profit, 2),
            "winrate_pct": round(self.wins / self.bets * 100, 2) if self.bets else None,
            "roi_pct": round(self.profit / self.bets * 100, 2) if self.bets else None,
        }


@dataclass
class OptimalRange:
    odds_min: float
    odds_max: float
    bets: int
    profit: float
    roi_pct: Optional[float]
    winrate_pct: Optional[float]


def odds_buckets(min_odds: float = 1.1, max_odds: float = 4.0, step: float = 0.1) -> List[float]:
    levels: List[float] = []
    value = min_odds
    while value <= max_odds + 1e-9:
        levels.append(round(value, 1))
        value = round(value + step, 1)
    return levels


def bucket_odds(odds: float, levels: List[float]) -> Optional[float]:
    if odds < 1.05:
        return None
    if odds >= levels[-1] - 0.05:
        return levels[-1]
    bucket = round(round(odds * 10) / 10, 1)
    if bucket < levels[0] or bucket > levels[-1]:
        return None
    return bucket


def _add_bucket(cells: Dict[float, BucketStats], level: float, won: Optional[bool], odds: float) -> None:
    cell = cells.setdefault(level, BucketStats())
    if won is None:
        cell.pushes += 1
        return
    cell.bets += 1
    cell.profit += profit_for_result(won, odds)
    if won:
        cell.wins += 1


def _find_best_contiguous_range(cells: Dict[float, BucketStats], levels: List[float]) -> Optional[OptimalRange]:
    """Лучший непрерывный диапазон кф (по суммарной прибыли, мин. 5 ставок)."""
    best: Optional[OptimalRange] = None
    n = len(levels)
    for i in range(n):
        agg = BucketStats()
        for j in range(i, n):
            cell = cells.get(levels[j], BucketStats())
            agg.bets += cell.bets
            agg.wins += cell.wins
            agg.pushes += cell.pushes
            agg.profit += cell.profit
            if agg.bets < 5:
                continue
            roi = agg.profit / agg.bets * 100
            candidate = OptimalRange(
                odds_min=levels[i],
                odds_max=levels[j],
                bets=agg.bets,
                profit=round(agg.profit, 2),
                roi_pct=round(roi, 2),
                winrate_pct=round(agg.wins / agg.bets * 100, 2) if agg.bets else None,
            )
            if best is None or candidate.profit > best.profit:
                best = candidate
    return best


def _best_single_bucket(cells: Dict[float, BucketStats], levels: List[float], min_bets: int = 5) -> Optional[dict]:
    best_level = None
    best_profit = None
    for level in levels:
        cell = cells.get(level)
        if not cell or cell.bets < min_bets:
            continue
        if best_profit is None or cell.profit > best_profit:
            best_profit = cell.profit
            best_level = level
    if best_level is None:
        return None
    cell = cells[best_level]
    return {"odds_bucket": best_level, **cell.to_dict()}


@dataclass
class SportBacktest:
    sport_id: int
    sport_name: str
    total_matches: int = 0
    with_favorite: int = 0
    win_settled: int = 0
    handicap_settled: int = 0
    skipped_no_1x2: int = 0
    skipped_no_handicap: int = 0
    win_by_odds: Dict[float, BucketStats] = field(default_factory=dict)
    handicap_by_bet_odds: Dict[float, BucketStats] = field(default_factory=dict)
    handicap_by_max_odds: Dict[float, BucketStats] = field(default_factory=dict)

    def to_dict(self, levels: List[float]) -> dict:
        win_cells = {str(k): v.to_dict() for k, v in sorted(self.win_by_odds.items())}
        hcap_cells = {str(k): v.to_dict() for k, v in sorted(self.handicap_by_bet_odds.items())}
        hcap_max_cells = {str(k): v.to_dict() for k, v in sorted(self.handicap_by_max_odds.items())}

        win_best = _best_single_bucket(self.win_by_odds, levels)
        hcap_best = _best_single_bucket(self.handicap_by_bet_odds, levels)
        win_range = _find_best_contiguous_range(self.win_by_odds, levels)
        hcap_range = _find_best_contiguous_range(self.handicap_by_bet_odds, levels)

        win_total = BucketStats()
        hcap_total = BucketStats()
        for cell in self.win_by_odds.values():
            win_total.bets += cell.bets
            win_total.wins += cell.wins
            win_total.profit += cell.profit
        for cell in self.handicap_by_bet_odds.values():
            hcap_total.bets += cell.bets
            hcap_total.wins += cell.wins
            hcap_total.profit += cell.profit

        return {
            "sport_id": self.sport_id,
            "sport_name": self.sport_name,
            "total_matches": self.total_matches,
            "with_favorite": self.with_favorite,
            "win_settled": self.win_settled,
            "handicap_settled": self.handicap_settled,
            "skipped_no_1x2": self.skipped_no_1x2,
            "skipped_no_handicap": self.skipped_no_handicap,
            "win_all_bets": win_total.to_dict(),
            "handicap_all_bets": hcap_total.to_dict(),
            "win_by_odds": win_cells,
            "handicap_by_bet_odds": hcap_cells,
            "handicap_by_max_odds": hcap_max_cells,
            "optimal_win_odds_bucket": win_best,
            "optimal_handicap_odds_bucket": hcap_best,
            "optimal_win_odds_range": (
                {
                    "odds_min": win_range.odds_min,
                    "odds_max": win_range.odds_max,
                    "bets": win_range.bets,
                    "profit": win_range.profit,
                    "roi_pct": win_range.roi_pct,
                    "winrate_pct": win_range.winrate_pct,
                }
                if win_range
                else None
            ),
            "optimal_handicap_odds_range": (
                {
                    "odds_min": hcap_range.odds_min,
                    "odds_max": hcap_range.odds_max,
                    "bets": hcap_range.bets,
                    "profit": hcap_range.profit,
                    "roi_pct": hcap_range.roi_pct,
                    "winrate_pct": hcap_range.winrate_pct,
                }
                if hcap_range
                else None
            ),
        }


def run_backtest(
    matches: List[FinishedMatch],
    *,
    odds_min: float = 1.1,
    odds_max: float = 4.0,
    odds_step: float = 0.1,
) -> Dict[str, Any]:
    levels = odds_buckets(odds_min, odds_max, odds_step)
    by_sport: Dict[int, SportBacktest] = {}

    for match in matches:
        sport_id = match.sport
        if sport_id not in by_sport:
            by_sport[sport_id] = SportBacktest(
                sport_id=sport_id,
                sport_name=sport_label(sport_id),
            )
        sport = by_sport[sport_id]
        sport.total_matches += 1

        fav = identify_favorite(match.odds.get("1X2_1"), match.odds.get("1X2_2"))
        if not fav:
            sport.skipped_no_1x2 += 1
            continue
        sport.with_favorite += 1

        h, a = match.score_home, match.score_away

        # Победа фаворита
        win_bucket = bucket_odds(fav.win_odds, levels)
        if win_bucket is not None:
            won = settle_win(h, a, fav.side)
            _add_bucket(sport.win_by_odds, win_bucket, won, fav.win_odds)
            sport.win_settled += 1

        # Фора фаворита
        hcap_lines = favorite_handicap_lines(match.odds, fav.side)
        selection = select_handicap_bet_line(hcap_lines)
        if not selection:
            sport.skipped_no_handicap += 1
            continue

        hcap_won = settle_handicap(
            h,
            a,
            selection["side"],
            selection["handicap_value"],
        )
        bet_bucket = bucket_odds(selection["bet_odds"], levels)
        max_bucket = bucket_odds(selection["max_odds"], levels)
        if bet_bucket is not None:
            _add_bucket(sport.handicap_by_bet_odds, bet_bucket, hcap_won, selection["bet_odds"])
        if max_bucket is not None:
            _add_bucket(sport.handicap_by_max_odds, max_bucket, hcap_won, selection["bet_odds"])
        sport.handicap_settled += 1

    sports_report = [by_sport[sid].to_dict(levels) for sid in sorted(by_sport.keys())]

    totals_win = BucketStats()
    totals_hcap = BucketStats()
    for s in by_sport.values():
        for cell in s.win_by_odds.values():
            totals_win.bets += cell.bets
            totals_win.wins += cell.wins
            totals_win.profit += cell.profit
        for cell in s.handicap_by_bet_odds.values():
            totals_hcap.bets += cell.bets
            totals_hcap.wins += cell.wins
            totals_hcap.profit += cell.profit

    return {
        "odds_grid": {"min": odds_min, "max": odds_max, "step": odds_step, "levels": levels},
        "totals": {
            "matches": len(matches),
            "sports": len(by_sport),
            "win_bets": totals_win.to_dict(),
            "handicap_bets": totals_hcap.to_dict(),
        },
        "by_sport": sports_report,
    }
