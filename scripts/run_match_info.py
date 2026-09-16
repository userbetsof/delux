"""Снимок инфо о матче (стадион, город, судья, зрители) из Flashscore df_sui."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db import create_database, get_db_connection  # noqa: E402
from match_snapshot import describe_match_info, save_match_info  # noqa: E402
from settings import DeluxSettings  # noqa: E402


def _targets(match_id: str, new_only: bool, limit: int) -> list[tuple[str, int]]:
    if match_id:
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT match_id, sport FROM matches WHERE match_id = ?",
                (match_id,),
            ).fetchone()
        sport = int(row["sport"] or 1) if row else 1
        return [(match_id, sport)]

    sql = """
        SELECT m.match_id, m.sport
        FROM matches m
        LEFT JOIN match_snapshot s ON s.match_id = m.match_id
    """
    if new_only:
        sql += " WHERE s.match_id IS NULL"
    sql += " ORDER BY m.match_date DESC"
    with get_db_connection() as conn:
        rows = conn.execute(sql).fetchall()
    out = [(str(r["match_id"]), int(r["sport"] or 1)) for r in rows if r["match_id"]]
    return out[:limit] if limit > 0 else out


def run_match_info(*, match_id: str = "", new_only: bool = False, limit: int = 0) -> dict:
    create_database()
    cfg = DeluxSettings.from_env()
    sourcer = cfg.match_settings.sourcer
    targets = _targets(match_id, new_only, limit)
    print(f"[*] Инфо о матчах: {len(targets)}")

    ok = skip = fail = 0
    for idx, (mid, sport) in enumerate(targets, 1):
        if idx > 1:
            time.sleep(0.15)
        try:
            info = save_match_info(mid, sport=sport, sourcer=sourcer)
        except Exception as exc:
            fail += 1
            print(f"[{idx}/{len(targets)}] {mid}: [-] {exc}")
            continue
        if not info:
            skip += 1
            print(f"[{idx}/{len(targets)}] {mid}: [-] нет данных в фиде")
            continue
        ok += 1
        print(f"[{idx}/{len(targets)}] {mid}: [+] {describe_match_info(info)}")

    summary = {"total": len(targets), "ok": ok, "skip": skip, "fail": fail}
    print(f"\n[+] Инфо о матчах: saved={ok} skip={skip} fail={fail}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Снимок инфо о матче (df_sui)")
    parser.add_argument("--match-id", default="")
    parser.add_argument("--new", action="store_true", help="Только матчи без снимка")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    summary = run_match_info(match_id=args.match_id, new_only=args.new, limit=args.limit)
    return 0 if summary.get("fail", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
