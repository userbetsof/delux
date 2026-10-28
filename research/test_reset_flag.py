"""Проверка reset_matches на копии БД."""

import os
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(r"C:\papki\work\bets\delux")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

src = ROOT / "matches.db"
dst = ROOT / "research" / "_test_reset.db"
for suffix in ("", "-wal", "-shm"):
    p = Path(str(dst) + suffix)
    if p.exists():
        p.unlink()
shutil.copy(src, dst)
os.environ["DATABASE_PATH"] = str(dst)

from analyze_match import reset_matches  # noqa: E402

IDS = ["25Xg8KYr", "xh92vrFN", "U35idt2t"]


def snap(tables, ids):
    conn = sqlite3.connect(dst)
    out = {}
    ph = ",".join("?" for _ in ids)
    for t in tables:
        try:
            out[t] = conn.execute(
                f'SELECT COUNT(*) FROM "{t}" WHERE match_id IN ({ph})', ids
            ).fetchone()[0]
        except sqlite3.OperationalError:
            out[t] = "n/a"
    out["matches.prediction"] = conn.execute(
        f"SELECT COUNT(*) FROM matches WHERE match_id IN ({ph}) "
        "AND prediction IS NOT NULL AND TRIM(prediction) <> ''",
        ids,
    ).fetchone()[0]
    conn.close()
    return out


tables = [
    "strategy_predictions",
    "odds",
    "outcome_probabilities",
    "goal_probabilities",
    "match_snapshot",
    "match_weather",
    "match_stats",
    "match_missing_players",
    "moneyway",
    "whoscored_preview",
    "match_queue",
    "team_matches_cache",
]

before = snap(tables, IDS)
print("ДО:")
for k, v in before.items():
    print(f"  {k:24} {v}")

print("\nDRY-RUN:")
dry = reset_matches(IDS, dry_run=True)
for k, v in dry.items():
    print(f"  {k:24} {v}")

after_dry = snap(tables, IDS)
print("  (данные не изменились:", before == after_dry, ")")

print("\nRESET:")
counts = reset_matches(IDS)
for k, v in counts.items():
    print(f"  {k:24} {v}")

after = snap(tables, IDS)
print("\nПОСЛЕ:")
for k, v in after.items():
    print(f"  {k:24} {v}")

print("\nпроверки:")
print("  справочники не тронуты:", after["match_queue"] == before["match_queue"],
      "| кэш команд не тронут:", after["team_matches_cache"] == before["team_matches_cache"])
print("  прогнозы очищены:", after["matches.prediction"] == 0)
print("  strategy_predictions очищены:", after["strategy_predictions"] == 0)
