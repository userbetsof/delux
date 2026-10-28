"""Проверка качества времени матчей и пригодности для rolling-формы."""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

DB = Path(r"C:\papki\work\bets\delux\matches.db")
FIN = "match_status='Завершен' AND score_home IS NOT NULL AND score_away IS NOT NULL"


def main() -> int:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    print("=== качество match_date / start_ts ===")
    for label, cond in (
        ("все", "1=1"),
        ("завершённые", FIN),
    ):
        tot = cur.execute(f"SELECT COUNT(*) FROM matches WHERE {cond}").fetchone()[0]
        empty_d = cur.execute(
            f"SELECT COUNT(*) FROM matches WHERE {cond} AND (match_date IS NULL OR TRIM(match_date)='')"
        ).fetchone()[0]
        bad_ts = cur.execute(
            f"SELECT COUNT(*) FROM matches WHERE {cond} AND (start_ts IS NULL OR start_ts<=0)"
        ).fetchone()[0]
        print(f"  {label}: n={tot} пустой match_date={empty_d} нет start_ts={bad_ts}")

    print("\n=== пустые даты по видам спорта (завершённые) ===")
    for row in cur.execute(
        f"SELECT sport, COUNT(*) n, SUM(CASE WHEN match_date IS NULL OR TRIM(match_date)='' THEN 1 ELSE 0 END) empty_d "
        f"FROM matches WHERE {FIN} GROUP BY sport"
    ):
        print(f"  sport={row['sport']}: n={row['n']} пустых={row['empty_d']}")

    print("\n=== примеры пустых дат ===")
    for row in cur.execute(
        f"SELECT match_id, match_date, start_ts, sport, league_id, score_home, score_away FROM matches "
        f"WHERE {FIN} AND (match_date IS NULL OR TRIM(match_date)='') LIMIT 10"
    ):
        print("  ", dict(row))

    print("\n=== start_ts примеры и масштаб ===")
    for row in cur.execute("SELECT match_id, match_date, start_ts FROM matches LIMIT 5"):
        print("  ", dict(row))

    print("\n=== сколько завершённых матчей имеет >= N предыдущих по команде (sport, лига) ===")
    rows = cur.execute(
        f"SELECT match_id, sport, league_id, home_team_id, away_team_id, match_date, start_ts "
        f"FROM matches WHERE {FIN}"
    ).fetchall()
    print(f"  всего завершённых: {len(rows)}")

    # порядок по (match_date, start_ts, match_id)
    def key(r):
        return (str(r["match_date"] or ""), int(r["start_ts"] or 0), str(r["match_id"]))

    per_sport = defaultdict(list)
    per_sport_league = defaultdict(list)
    for r in rows:
        per_sport[r["sport"]].append(r)
        per_sport_league[(r["sport"], r["league_id"])].append(r)

    team_hist = defaultdict(list)
    team_hist_league = defaultdict(list)
    for sport, items in per_sport.items():
        for r in sorted(items, key=key):
            team_hist[(sport, r["home_team_id"])].append(r)
            team_hist[(sport, r["away_team_id"])].append(r)
    for (sport, league), items in per_sport_league.items():
        for r in sorted(items, key=key):
            team_hist_league[(sport, league, r["home_team_id"])].append(r)
            team_hist_league[(sport, league, r["away_team_id"])].append(r)

    def coverage(hist_outer, hist_inner, tag):
        for sport, items in sorted(per_sport.items()):
            both10 = both1 = both0 = 0
            for r in sorted(items, key=key):
                hs = hist_outer[(sport, r["home_team_id"])]
                as_ = hist_outer[(sport, r["away_team_id"])]
                kh = key(r)
                nh = len([x for x in hs if key(x) < kh])
                na = len([x for x in as_ if key(x) < kh])
                if nh >= 10 and na >= 10:
                    both10 += 1
                if nh >= 1 and na >= 1:
                    both1 += 1
                if nh == 0 or na == 0:
                    both0 += 1
            print(f"  [{tag}] sport={sport}: n={len(items)} обе>=10: {both10} ({both10/len(items):.1%}) "
                  f"обе>=1: {both1} ({both1/len(items):.1%}) хотя бы одна без истории: {both0}")

    coverage(team_hist, team_hist_league, "по виду спорта")
    coverage(team_hist_league, team_hist_league, "по лиге")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
