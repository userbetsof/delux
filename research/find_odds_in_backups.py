import gzip
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BACKUPS = Path(r"C:\papki\work\bets\delux\backups\db")
MID = "6mdpltmc"

for gz in sorted(BACKUPS.glob("matches_*.db.gz"), reverse=True)[:6]:
    tmp = Path(tempfile.gettempdir()) / "_check_backup.db"
    try:
        with gzip.open(gz, "rb") as src, open(tmp, "wb") as dst:
            shutil.copyfileobj(src, dst)
        conn = sqlite3.connect(str(tmp))
        odds = conn.execute(
            "SELECT COUNT(*) FROM odds WHERE match_id = ?", (MID,)
        ).fetchone()[0]
        oc = conn.execute(
            "SELECT COUNT(*) FROM outcome_probabilities WHERE match_id = ?", (MID,)
        ).fetchone()[0]
        nz = conn.execute(
            "SELECT COUNT(*) FROM outcome_probabilities WHERE match_id = ? "
            "AND (COALESCE(home_win_prob,0)+COALESCE(draw_prob,0)"
            "     +COALESCE(away_win_prob,0)) > 0",
            (MID,),
        ).fetchone()[0]
        sp = conn.execute(
            "SELECT COUNT(*) FROM strategy_predictions WHERE match_id = ?", (MID,)
        ).fetchone()[0]
        conn.close()
        print(f"{gz.name}: odds={odds} outcome={oc} (ненулевых {nz}) прогнозов={sp}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"{gz.name}: ERR {exc}")
    finally:
        tmp.unlink(missing_ok=True)
