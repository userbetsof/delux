"""Валидация восстановленной таблицы: сверка с финальной таблицей to_ feed и проверка снимков."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from test_flashscore import parse_to_feed  # noqa: E402

DB = ROOT / "test_flashscore.db"


def main() -> int:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # --- 1. финальная таблица из to_ feed ---
    raw = cur.execute(
        "SELECT raw_data FROM feed_snapshots WHERE feed_type='to_overall' ORDER BY id DESC LIMIT 1"
    ).fetchone()["raw_data"]
    official = {t["team"]: t for t in parse_to_feed(raw, table_index=1)}

    # --- 2. финальная таблица из снимка последнего матча ---
    last = cur.execute(
        "SELECT match_id, snapshot_date FROM standings_snapshot "
        "ORDER BY snapshot_date DESC, match_id DESC LIMIT 1"
    ).fetchone()
    rows = cur.execute(
        "SELECT team_name, rank, played, wins, draws, losses, scored, conceded, points "
        "FROM standings_snapshot WHERE match_id = ? ORDER BY rank",
        (last["match_id"],),
    ).fetchall()
    reconstructed = {r["team_name"]: dict(r) for r in rows}

    print(f"последний снимок: {last['match_id']} @ {last['snapshot_date']}")
    print(f"команд в финальной таблице: официально={len(official)}, восстановлено={len(reconstructed)}")

    # --- 3. сверка по каждой команде ---
    mismatches = 0
    for team, off in official.items():
        rec = reconstructed.get(team)
        if rec is None:
            print(f"  [НЕТ КОМАНДЫ] {team}")
            mismatches += 1
            continue
        for field in ("played", "wins", "draws", "losses", "scored", "conceded", "points"):
            ov = int(off[field])
            rv = int(rec[field])
            if ov != rv:
                print(f"  [РАСХОЖДЕНИЕ] {team}.{field}: офиц={ov} восст={rv}")
                mismatches += 1
    print(f"расхождений в финальной таблице: {mismatches}")

    # --- 4. покрытие снимками: у каждого матча должна быть таблица на 20 команд ---
    n_matches = cur.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    n_snap = cur.execute(
        "SELECT COUNT(DISTINCT match_id) FROM standings_snapshot"
    ).fetchone()[0]
    per_match = cur.execute(
        "SELECT MIN(c), MAX(c) FROM (SELECT COUNT(*) c FROM standings_snapshot GROUP BY match_id)"
    ).fetchone()
    print(f"матчей={n_matches}, матчей со снимком={n_snap}, команд в снимке: min={per_match[0]} max={per_match[1]}")

    # --- 5. проверка суммы: сумма очков всех команд в снимке == 3*W + 1*D по сыгранным матчам ---
    # для снимка на конкретную дату сумма played = 2 * (число матчей до этой даты)
    sample_date = "2015.12.26 18:00"  # boxing day, середина сезона
    snap_row = cur.execute(
        "SELECT match_id FROM standings_snapshot WHERE snapshot_date = ? LIMIT 1",
        (sample_date,),
    ).fetchone()
    if snap_row:
        srows = cur.execute(
            "SELECT SUM(played) sp, SUM(points) spts, SUM(wins) sw, SUM(draws) sd, SUM(losses) sl "
            "FROM standings_snapshot WHERE match_id = ?",
            (snap_row["match_id"],),
        ).fetchone()
        prior = cur.execute(
            "SELECT COUNT(*) FROM matches WHERE match_date < ?", (sample_date,)
        ).fetchone()[0]
        print(f"\nснимок @ {sample_date} (match {snap_row['match_id']}):")
        print(f"  sum(played)={srows['sp']} (ожид. 2*{prior}={2*prior})")
        print(f"  sum(points)={srows['spts']}, sum(wins)={srows['sw']}, sum(draws)={srows['sd']}, sum(losses)={srows['sl']}")
        print(f"  проверка points=3*W+D: {3*(srows['sw'] or 0)+(srows['sd'] or 0)}")
        print(f"  проверка W+D+L=played: {srows['sw']+srows['sd']+srows['sl']} == {srows['sp']}")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
