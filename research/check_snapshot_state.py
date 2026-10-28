import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect(r"C:\papki\work\bets\delux\matches.db")
conn.row_factory = sqlite3.Row

for mid in ("Cfb5H9Sg", "runNPizJ", "6e5dszfS"):
    pred = conn.execute(
        "SELECT prediction FROM matches WHERE match_id = ?", (mid,)
    ).fetchone()
    n = conn.execute(
        "SELECT COUNT(*) FROM strategy_predictions WHERE match_id = ?", (mid,)
    ).fetchone()[0]
    snap = conn.execute(
        "SELECT standings_json IS NOT NULL AS st, h2h_json IS NOT NULL AS h2h, "
        "team_matches_json IS NOT NULL AS tm FROM match_snapshot WHERE match_id = ?",
        (mid,),
    ).fetchone()
    p = pred["prediction"] if pred else None
    st = snap["st"] if snap else None
    h2h = snap["h2h"] if snap else None
    tm = snap["tm"] if snap else None
    print(f"{mid}: prediction={p!r} стратегий={n} st={st} h2h={h2h} tm={tm}")
