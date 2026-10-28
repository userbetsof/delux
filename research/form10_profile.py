"""Профилирование matches.db под задачу: форма команды за последние 10 матчей -> 1x2."""
from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

DB = Path(r"C:\papki\work\bets\delux\matches.db")


def q(cur, sql, params=()):
    return cur.execute(sql, params).fetchall()


def main() -> int:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    print("=" * 70)
    print("TEAM_FORM_STATS (существующая таблица формы)")
    print("=" * 70)
    try:
        cols = [r[1] for r in q(cur, "PRAGMA table_info(team_form_stats)")]
        print("cols:", cols)
        print("rows:", q(cur, "SELECT COUNT(*) FROM team_form_stats")[0][0])
        for row in q(cur, "SELECT * FROM team_form_stats LIMIT 5"):
            print("  ", dict(row))
    except Exception as exc:  # noqa: BLE001
        print("ERR", exc)

    print()
    print("=" * 70)
    print("MATCHES по видам спорта")
    print("=" * 70)
    fin = "match_status='Завершен' AND score_home IS NOT NULL AND score_away IS NOT NULL"
    for (sport,) in q(cur, "SELECT DISTINCT sport FROM matches ORDER BY sport"):
        total = q(cur, "SELECT COUNT(*) FROM matches WHERE sport=?", (sport,))[0][0]
        finn = q(cur, f"SELECT COUNT(*) FROM matches WHERE sport=? AND {fin}", (sport,))[0][0]
        hw = q(cur, f"SELECT COUNT(*) FROM matches WHERE sport=? AND {fin} AND score_home>score_away", (sport,))[0][0]
        dr = q(cur, f"SELECT COUNT(*) FROM matches WHERE sport=? AND {fin} AND score_home=score_away", (sport,))[0][0]
        aw = q(cur, f"SELECT COUNT(*) FROM matches WHERE sport=? AND {fin} AND score_home<score_away", (sport,))[0][0]
        lo, hi = q(cur, f"SELECT MIN(match_date), MAX(match_date) FROM matches WHERE sport=? AND {fin}", (sport,))[0]
        print(f"sport={sport}: total={total} finished={finn} "
              f"1x2={hw}/{dr}/{aw} ({hw/max(finn,1):.1%}/{dr/max(finn,1):.1%}/{aw/max(finn,1):.1%}) "
              f"dates={lo} .. {hi}")

    print()
    print("=" * 70)
    print("Покрытие команд историей (только завершённые)")
    print("=" * 70)
    rows = q(cur, f"SELECT sport, home_team_id, away_team_id, match_date, start_ts FROM matches WHERE {fin}")
    by_sport = defaultdict(list)
    for r in rows:
        by_sport[r["sport"]].append(r)
    for sport, items in sorted(by_sport.items()):
        cnt = Counter()
        for r in items:
            cnt[r["home_team_id"]] += 1
            cnt[r["away_team_id"]] += 1
        dist = Counter()
        for team, n in cnt.items():
            dist[min(n, 30)] += 1
        ge10 = sum(1 for n in cnt.values() if n >= 10)
        print(f"sport={sport}: teams={len(cnt)} teams_with_>=10_finished={ge10}")
        print(f"   матчей на команду (обрезано на 30): {sorted(dist.items())}")

    print()
    print("=" * 70)
    print("Целостность связей и дубликатов")
    print("=" * 70)
    orphan_home = q(cur, "SELECT COUNT(*) FROM matches m LEFT JOIN teams t ON t.id=m.home_team_id WHERE t.id IS NULL")[0][0]
    orphan_away = q(cur, "SELECT COUNT(*) FROM matches m LEFT JOIN teams t ON t.id=m.away_team_id WHERE t.id IS NULL")[0][0]
    print(f"матчей с home_team_id без записи в teams: {orphan_home}")
    print(f"матчей с away_team_id без записи в teams: {orphan_away}")
    dup = q(cur, "SELECT match_id, COUNT(*) c FROM matches GROUP BY match_id HAVING c>1")[0][0]
    print(f"дубликатов match_id: {dup if isinstance(dup, int) else dup}")
    dups = q(cur, "SELECT COUNT(*) FROM (SELECT match_id FROM matches GROUP BY match_id HAVING COUNT(*)>1)")
    print(f"групп дубликатов match_id: {dups[0][0]}")
    if dups[0][0]:
        for row in q(cur, "SELECT match_id, COUNT(*) c FROM matches GROUP BY match_id HAVING c>1 LIMIT 10"):
            print("   dup:", dict(row))

    print()
    print("  start_ts наличие:")
    print("   ", q(cur, "SELECT COUNT(*) FROM matches WHERE start_ts IS NULL OR start_ts=0")[0][0], "без start_ts")
    print("    match_date примеры:", [r[0] for r in q(cur, "SELECT match_date FROM matches LIMIT 3")])
    print("    start_ts примеры:", [r[0] for r in q(cur, "SELECT start_ts FROM matches LIMIT 3")])

    print()
    print("=" * 70)
    print("Спорт: справочник sports")
    print("=" * 70)
    for row in q(cur, "SELECT * FROM sports LIMIT 20"):
        print("  ", dict(row))

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
