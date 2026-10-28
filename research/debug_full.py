"""Full debug: evaluate formulas and check outcome_probabilities."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from formula_port.workbook_loader import has_formula_cache
from formula_port.engine import PythonCalcEngine
from analysis_data import load_analysis_data
from odds_service import load_odds
from settings import DeluxSettings
from match_store import get_queued_match
from analysis_data import build_settings

if not has_formula_cache():
    print("[!] Нет формульного кэша")
    sys.exit(1)

# Get a match from queue
import sqlite3
con = sqlite3.connect('matches.db')
con.row_factory = sqlite3.Row
row = con.execute('SELECT match_id, sport FROM match_queue LIMIT 1').fetchone()
con.close()

if not row:
    print("[!] No match in queue")
    sys.exit(1)

match_id = row['match_id']
sport = row['sport']
print(f"Match: {match_id} (sport={sport})")

# Load queued match
queued = get_queued_match(match_id)
if not queued:
    print(f"[!] Match {match_id} not in queue")
    sys.exit(1)

match = queued.to_match_info()
print(f"  Teams: {match.home} vs {match.away}")

# Load settings
cfg = DeluxSettings.from_env()
ms = build_settings(
    sport=queued.sport,
    source=cfg.source,
    tz_base=cfg.tz_base,
    dayzone_base=cfg.dayzone_base,
    time_offset=cfg.time_offset,
)

# Load odds
code, odds_data = load_odds(match_id, cfg.source)
if code != 0 or odds_data is None:
    print(f"  [!] odds code={code}")
    odds_data = None

# Build payload
payload = load_analysis_data(match, ms)
print(f"  Payload: H2H={len(payload.h2h or [])}, Home={len(payload.home_all or [])}, Away={len(payload.away_all or [])}")

# Run PythonCalcEngine
try:
    engine = PythonCalcEngine("", pure_eval=True)
    results = engine.run(payload, odds_data)
    
    print("\n  Outcome probabilities (first 5 strategies):")
    for op in results.get("outcome_probabilities", [])[:5]:
        total = op['home_prob'] + op['draw_prob'] + op['away_prob']
        print(f"    strat {op['strategy_idx']}: H={op['home_prob']:.4f} D={op['draw_prob']:.4f} A={op['away_prob']:.4f} (sum={total:.4f})")
    
    # Check if probs are non-zero
    first = results.get("outcome_probabilities", [{}])[0]
    if first.get('home_prob', 0) == 0 and first.get('draw_prob', 0) == 0 and first.get('away_prob', 0) == 0:
        print("\n  [WARN] All probabilities are zero! Formula evaluation still failing.")
    else:
        print("\n  [OK] Probabilities are non-zero!")
    
except Exception as exc:
    print(f"[!] Error: {exc}")
    import traceback
    traceback.print_exc()

print("\n=== Done ===")
