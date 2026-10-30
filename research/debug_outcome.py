import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\papki\work\bets\delux")

from settings import DeluxSettings
from analysis_data import MatchInfo, load_analysis_data
from calc_backend import get_calc_engine

cfg = DeluxSettings.from_env()
ms = cfg.match_settings

m = MatchInfo(match_id="6mdpltmc")
m.status = 3
m.start_ts = 1452714300

payload = load_analysis_data(m, ms)
print("таблица:", len(payload.table_overall), "строк")
print("форма overall:", len(payload.form_overall), "строк")
print("форма home:", len(payload.form_home), "строк")
print("форма away:", len(payload.form_away), "строк")

eng = get_calc_engine(cfg)
from odds_service import load_odds
ok, odds_data = load_odds('6mdpltmc', cfg.source)
print('odds code:', ok)
res = eng.run(payload, odds_data, list_odds=[])
op = res.get("outcome_probabilities") or []
print()
print("outcome_probabilities из движка:")
for item in op:
    print("  ", item)
print()
gp_h = res.get("home_goals") or []
gp_a = res.get("away_goals") or []
print("home_goals:", gp_h)
print("away_goals:", gp_a)
