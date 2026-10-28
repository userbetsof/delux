"""Debug match Qg22AywS with full traceback."""
import traceback, sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from match_analysis import analyze_match
from analysis_data import MatchInfo, build_settings
from match_store import QueuedMatch
from settings import DeluxSettings

queued = QueuedMatch(
    match_id='Qg22AywS',
    sport=1,
    home_name='Лестер',
    away_name='Сандерленд',
    tour_name='АНГЛИЯ: Премьер-лига'
)
queued.start_ts = 1439042400
match = queued.to_match_info()

cfg = DeluxSettings.from_env()
ms = build_settings(sport=1, source=cfg.source, tz_base=cfg.tz_base, dayzone_base=cfg.dayzone_base, time_offset=cfg.time_offset)

try:
    analyze_match('', match, ms, queued=queued)
except Exception as e:
    traceback.print_exc()
