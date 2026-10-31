import gzip
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BACKUPS = Path(r"C:\papki\work\bets\delux\backups\db")
LIVE = r"C:\papki\work\bets\delux\matches.db"

live = sqlite3.connect(LIVE)
missing = [
    r[0]
    for r in live.execute(
        """
        SELECT o.match_id FROM outcome_probabilities o
        WHERE NOT EXISTS (SELECT 1 FROM match_snapshot s WHERE s.match_id = o.match_id)
        GROUP BY o.match_id
        """
    ).fetchall()
]
live.close()
print(f"матчей без снимка: {len(missing)}")

found = {}
for gz in sorted(BACKUPS.glob("matches_*.db.gz"), reverse=True):
    tmp = Path(tempfile.gettempdir()) / "_scan.db"
    try:
        with gzip.open(gz, "rb") as src, open(tmp, "wb") as dst:
            shutil.copyfileobj(src, dst)
        conn = sqlite3.connect(str(tmp))
        for mid in missing:
            if mid in found:
                continue
            n = conn.execute(
                "SELECT COUNT(*) FROM match_snapshot WHERE match_id = ?", (mid,)
            ).fetchone()[0]
            if n:
                found[mid] = gz.name
        conn.close()
    except Exception:  # noqa: BLE001
        continue
    finally:
        tmp.unlink(missing_ok=True)

print(f"найдено в снимках БД: {len(found)}")
for mid, name in list(found.items())[:10]:
    print(f"  {mid} <- {name}")
