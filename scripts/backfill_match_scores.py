"""Backfill match scores from flashscorekz df_sui feed into matches.db."""
from __future__ import annotations

import os
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from flashscore_feed import API_HEADERS, FLASHSCORE_HOST, parse_fields  # noqa: E402

HOSTS = (FLASHSCORE_HOST,)


def fetch_sui(match_id: str, sport: int = 1) -> str | None:
    for host in HOSTS:
        url = f"https://{host}/x/feed/df_sui_{sport}_{match_id}"
        try:
            req = urllib.request.Request(
                url,
                headers={**API_HEADERS, "User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception:
            continue
    return None


def parse_score(body: str, sport: int) -> tuple[int | None, int | None, str]:
    """Return (home, away, status_hint)."""
    last_inx = last_iox = None
    period_home = period_away = 0
    period_rows = 0
    has_finished_marker = False
    period_names: list[str] = []

    for row in body.split("~"):
        if not row:
            continue
        data = parse_fields(row.split("¬"))
        if not data:
            continue
        if "INX" in data and "IOX" in data:
            try:
                last_inx = int(float(data["INX"]))
                last_iox = int(float(data["IOX"]))
            except ValueError:
                pass
        if data.get("AC"):
            period_names.append(str(data["AC"]))
            try:
                period_home += int(float(data.get("IG") or 0))
                period_away += int(float(data.get("IH") or 0))
                period_rows += 1
            except ValueError:
                pass
            ac = str(data["AC"]).lower()
            if any(x in ac for x in ("finished", "ended", "after", "penalt", "full time", "ft")):
                has_finished_marker = True
        # baseball final sometimes WF/WG
        if sport == 6 and "WF" in data and "WG" in data:
            try:
                return int(float(data["WF"])), int(float(data["WG"])), "Завершен"
            except ValueError:
                pass

    if last_inx is not None and last_iox is not None:
        if has_finished_marker or period_rows >= (9 if sport == 6 else 2):
            return last_inx, last_iox, "Завершен"
        # live / not finished — keep score but don't force finished unless non-zero periods
        if period_rows > 0 and (last_inx + last_iox) > 0:
            return last_inx, last_iox, "unknown"
        return None, None, "unknown"

    if period_rows > 0:
        # football: 2 halves; baseball: 9 innings
        enough = period_rows >= (9 if sport == 6 else 2)
        if enough:
            return period_home, period_away, "Завершен"
        if period_home + period_away > 0:
            return period_home, period_away, "unknown"

    return None, None, "unknown"


def main():
    args = [a for a in sys.argv[1:] if a != "--all"]
    only_pred = "--all" not in sys.argv
    limit = int(args[0]) if args else 0
    conn = sqlite3.connect("matches.db")
    conn.row_factory = sqlite3.Row
    sql = """
        SELECT match_id, sport, prediction
        FROM matches
        WHERE match_status = 'Не начался'
    """
    if only_pred:
        sql += " AND prediction IS NOT NULL AND TRIM(prediction) NOT IN ('', '-')"
    sql += " ORDER BY match_date"
    rows = conn.execute(sql).fetchall()
    if limit:
        rows = rows[:limit]
    print(f"to update: {len(rows)} (only_pred={only_pred})")

    ok = fail = skip = 0
    for i, r in enumerate(rows, 1):
        mid = r["match_id"]
        sport = int(r["sport"] or 1)
        try:
            body = fetch_sui(mid, 1 if sport not in (1, 4, 6) else sport)
            if not body:
                fail += 1
                print(f"[{i}/{len(rows)}] {mid}: empty feed")
                continue
            home, away, status = parse_score(body, sport)
            if home is None or away is None:
                skip += 1
                if i <= 5 or i % 50 == 0:
                    print(f"[{i}/{len(rows)}] {mid}: no score")
                continue
            if status != "Завершен":
                skip += 1
                if i <= 5 or i % 50 == 0:
                    print(f"[{i}/{len(rows)}] {mid}: not finished yet ({home}:{away})")
                continue
            conn.execute(
                """
                UPDATE matches
                SET score_home=?, score_away=?, match_status=?
                WHERE match_id=?
                """,
                (home, away, status, mid),
            )
            conn.commit()
            ok += 1
            print(f"[{i}/{len(rows)}] {mid}: {home}:{away} ({status}) pred={r['prediction']}")
        except Exception as exc:
            fail += 1
            print(f"[{i}/{len(rows)}] {mid}: ERR {exc}")
        time.sleep(0.12)

    print(f"done ok={ok} skip={skip} fail={fail}")
    print(
        "finished:",
        conn.execute(
            "SELECT COUNT(*) FROM matches WHERE match_status='Завершен'"
        ).fetchone()[0],
    )
    print(
        "nonzero scores:",
        conn.execute(
            "SELECT COUNT(*) FROM matches WHERE score_home+score_away>0 OR match_status='Завершен'"
        ).fetchone()[0],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
