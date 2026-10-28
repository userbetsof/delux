import sys
import traceback

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

from analysis_data import MatchInfo, load_analysis_data
from settings import DeluxSettings
from match_analysis import _fetch_match_status

MATCH = sys.argv[1] if len(sys.argv) > 1 else "25Xg8KYr"

cfg = DeluxSettings.from_env()
settings = cfg.match_settings

status = _fetch_match_status(MATCH, settings.sport)
print("status:", status)

match = MatchInfo(match_id=MATCH)
match.status = status
payload = load_analysis_data(match, settings)
print("league:", match.league, "| home:", match.home, "| away:", match.away)
print("h2h:", len(payload.h2h or []))
for name in ("table_overall", "table_home", "table_away", "form_overall", "form_home", "form_away",
             "home_matches", "away_matches", "h2h"):
    rows = getattr(payload, name, None)
    if isinstance(rows, list):
        print(f"  {name}: {len(rows)}")
print("--- first h2h rows")
for r in (payload.h2h or [])[:3]:
    print("   ", r)
print("--- table_overall sample")
for r in (getattr(payload, "table_overall", None) or [])[:3]:
    print("   ", r)
