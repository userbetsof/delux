import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from settings import DeluxSettings
from match_store import get_queued_match
from analysis_data import build_settings
from calc_engine import ExcelCalcEngine
from odds_service import load_odds

cfg = DeluxSettings.from_env()
wb = cfg.resolve_calc_workbook()

conn = sqlite3.connect("matches.db")
conn.row_factory = sqlite3.Row

mids = sys.argv[1:] or ["25Ibkec6", "CCaFbHKD", "xzZYj8YA"]
for mid in mids:
    print(f"\n=== {mid} ===")
    rows = conn.execute(
        """
        SELECT o.strategy_id, s.strategy_name, o.home_win_prob, o.draw_prob, o.away_win_prob
        FROM outcome_probabilities o
        JOIN sub_strategies s ON s.id = o.strategy_id
        WHERE o.match_id = ?
        ORDER BY o.strategy_id
        """,
        (mid,),
    ).fetchall()
    sport = conn.execute("SELECT sport FROM matches WHERE match_id=?", (mid,)).fetchone()
    print("sport", sport[0] if sport else "?")
    for r in rows:
        print(
            f"  DB {r['strategy_id']:2} {r['strategy_name'][:14]:14} "
            f"H={r['home_win_prob']:.2f} D={r['draw_prob']:.2f} A={r['away_win_prob']:.2f}"
        )

    queued = get_queued_match(mid)
    if not queued:
        continue
    match = queued.to_match_info()
    ms = build_settings(
        sport=queued.sport,
        source=cfg.source,
        tz_base=cfg.tz_base,
        dayzone_base=cfg.dayzone_base,
        time_offset=cfg.time_offset,
    )
    code, odds = load_odds(mid, cfg.source)
    if code != 0 or odds is None:
        print("  odds unavailable", code)
        continue
    from analysis_data import load_analysis_data

    payload = load_analysis_data(match, ms)
    with ExcelCalcEngine(wb) as eng:
        eng.write_payload(payload)
        eng.write_odds(odds)
        eng.calculate()
        ws = eng.wb.Worksheets("Анализ")
        print("  Excel raw:")
        for i in range(10):
            row = 8 + i * 2
            h = ws.Range(f"H{row}").Value
            j = ws.Range(f"J{row}").Value
            k = ws.Range(f"K{row}").Value
            print(f"    strat {i+1} row {row}: H={h!r} J={j!r} K={k!r}")

conn.close()
