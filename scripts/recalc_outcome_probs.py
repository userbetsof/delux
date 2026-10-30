"""Пересчёт outcome_probabilities для матчей с нулевыми вероятностями.

Зачем: у части матчей в outcome_probabilities записаны нули (0/0/0),
хотя goal_probabilities есть. Такие матчи анализировались до исправления
движка и в БД остался мусор — в админке видно «1 пр» и «poisson»
с нулевыми вероятностями.

Скрипт для каждого затронутого матча:
  1. Загружает данные (таблица/форма/H2H/история).
  2. Считает вероятности движком.
  3. Пишет только строки, которые реально стали ненулевыми.
  4. Не трогает матчи, где расчёт тоже даёт нули (значит нет данных).

    py -3 scripts/recalc_outcome_probs.py --dry-run
    py -3 scripts/recalc_outcome_probs.py
    py -3 scripts/recalc_outcome_probs.py --limit 20 --strategy 1
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db import get_database_path, insert_outcome_probabilities_from_values  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass


def _zero_matches(conn: sqlite3.Connection, strategy_id: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT o.match_id
        FROM outcome_probabilities o
        JOIN matches m ON m.match_id = o.match_id
        WHERE o.strategy_id = ?
          AND (COALESCE(o.home_win_prob,0) + COALESCE(o.draw_prob,0)
               + COALESCE(o.away_win_prob,0)) = 0
        ORDER BY m.match_date
        """,
        (strategy_id,),
    ).fetchall()
    return [r[0] for r in rows]


def _payload_from_snapshot(match_id: str, sport: int, cfg=None):
    """Собрать payload из сохранённого снимка (таблица + форма) — без сети.

    Для пересчёта вероятностей исходов нужны только standings_json и
    form_json; H2H и история команд на исходы не влияют. Чтение снимка
    занимает миллисекунды вместо ~65 секунд загрузки из фидов.
    """
    import json

    from analysis_data import AnalysisPayload, MatchInfo, TableRow, build_settings

    with sqlite3.connect(str(get_database_path()), timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT standings_json, form_json FROM match_snapshot WHERE match_id = ?",
            (match_id,),
        ).fetchone()
    if row is None:
        return None

    def _to_table_rows(entries):
        """[dict, ...] из JSON снимка → [TableRow, ...]."""
        if isinstance(entries, dict):
            entries = [entries]
        out = []
        for item in entries or []:
            if not isinstance(item, dict) or not item.get("team"):
                continue
            out.append(
                TableRow(
                    rank=str(item.get("rank", "")),
                    team=str(item.get("team", "")),
                    played=str(item.get("played", "")),
                    wins=str(item.get("wins", "")),
                    draws=str(item.get("draws", "")),
                    losses=str(item.get("losses", "")),
                    scored=str(item.get("scored", "")),
                    conceded=str(item.get("conceded", "")),
                    points=str(item.get("points", "")),
                )
            )
        return out

    def _section(raw, key):
        """Достать секцию (overall/home/away) из JSON снимка."""
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return []
        if not isinstance(data, dict):
            return []
        return _to_table_rows(data.get(key) or [])

    payload = AnalysisPayload(match=MatchInfo(match_id=match_id), settings=None)
    # Все три среза таблицы и все три среза формы — движку нужны все шесть
    # (Расчеты! берут и overall, и home/away).
    payload.table_overall = _section(row["standings_json"], "overall")
    payload.table_home = _section(row["standings_json"], "home")
    payload.table_away = _section(row["standings_json"], "away")
    payload.form_overall = _section(row["form_json"], "overall")
    payload.form_home = _section(row["form_json"], "home")
    payload.form_away = _section(row["form_json"], "away")

    if not any(
        (
            payload.table_overall,
            payload.table_home,
            payload.table_away,
            payload.form_overall,
            payload.form_home,
            payload.form_away,
        )
    ):
        return None

    # Без формы стратегии дают 0/0/0 — догружаем её из сети только когда
    # в снимке её нет (старые записи). Это медленно, поэтому лишь при нужде.
    if not payload.form_overall:
        try:
            from analysis_data import fetch_table

            ms = build_settings(
                sport=sport,
                source=cfg.source,
                tz_base=cfg.tz_base,
                dayzone_base=cfg.dayzone_base,
                time_offset=cfg.time_offset,
            )
            payload.form_overall = fetch_table(ms, match_id, "form_overall")
            payload.form_home = fetch_table(ms, match_id, "form_home")
            payload.form_away = fetch_table(ms, match_id, "form_away")
            if payload.form_overall:
                # Дозаписываем в снимок, чтобы больше не ходить в сеть.
                try:
                    from db import upsert_match_snapshot
                    from match_snapshot import build_payload_snapshot

                    snap = build_payload_snapshot(payload)
                    if snap.get("form_json"):
                        upsert_match_snapshot(match_id, {"form_json": snap["form_json"]})
                except Exception:  # noqa: BLE001
                    pass
        except Exception as exc:  # noqa: BLE001
            print(f'    [!] форма из сети: {exc}')

    return payload


def _history_from_snapshot(match_id: str):
    """H2H и матчи команд из снимка — стратегии #1/#4 строят из них форму.

    Возвращает dict: h2h / home_all / away_all (пустые списки, если нет).
    """
    import json

    with sqlite3.connect(str(get_database_path()), timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT h2h_json, team_matches_json FROM match_snapshot "
            "WHERE match_id = ?",
            (match_id,),
        ).fetchone()
    out: dict = {"h2h": [], "home_all": [], "away_all": []}
    if row is None:
        return out

    def _load(raw):
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    out["h2h"] = list(_load(row["h2h_json"]).get("all") or [])
    tm = _load(row["team_matches_json"])
    for side in ("home", "away"):
        block = tm.get(side) or {}
        if isinstance(block, dict):
            out[f"{side}_all"] = list(block.get("all") or [])
    return out


def _recalc_one(match_id: str, cfg) -> list[dict] | None:
    """Посчитать вероятности для матча. None — не удалось."""
    from analysis_data import MatchInfo, build_settings, load_analysis_data
    from calc_backend import get_calc_engine

    row = None
    with sqlite3.connect(str(get_database_path()), timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT match_status, start_ts, sport FROM matches WHERE match_id = ?",
            (match_id,),
        ).fetchone()
    if row is None:
        return None

    sport = row["sport"] or 1
    ms = build_settings(
        sport=sport,
        source=cfg.source,
        tz_base=cfg.tz_base,
        dayzone_base=cfg.dayzone_base,
        time_offset=cfg.time_offset,
    )

    # Гибрид: сначала быстрый путь (снимок). Если ключевые стратегии
    # остались нулевыми — полная загрузка из сети, как при анализе.
    payload = _payload_from_snapshot(match_id, sport, cfg)

    if payload is None:
        info = MatchInfo(match_id=match_id)
        info.status = row["match_status"]
        info.start_ts = row["start_ts"]
        payload = load_analysis_data(info, ms)
        if not payload.table_overall and not payload.form_overall:
            return None

    payload.settings = ms
    payload.match = MatchInfo(match_id=match_id)
    payload.match.status = row["match_status"]
    payload.match.start_ts = row["start_ts"]

    # H2H и матчи команд: стратегии #1/#4 строят из них форму на дату матча.
    if not payload.h2h and not payload.home_all:
        try:
            from analysis_data import HistoryMatch

            hist = _history_from_snapshot(match_id)

            def _to_hm(item):
                if isinstance(item, HistoryMatch):
                    return item
                if not isinstance(item, dict):
                    return None
                try:
                    return HistoryMatch(**{
                        k: item.get(k, "")
                        for k in HistoryMatch.__dataclass_fields__
                    })
                except Exception:  # noqa: BLE001
                    return None

            payload.h2h = [h for h in (_to_hm(x) for x in hist["h2h"]) if h]
            payload.home_all = [h for h in (_to_hm(x) for x in hist["home_all"]) if h]
            payload.away_all = [h for h in (_to_hm(x) for x in hist["away_all"]) if h]
        except Exception as exc:  # noqa: BLE001
            print(f"    [!] история из снимка: {exc}")

    from odds_service import load_odds

    try:
        _code, odds_data = load_odds(match_id, cfg.source)
    except Exception:  # noqa: BLE001
        odds_data = None

    eng = get_calc_engine(cfg)
    res = eng.run(payload, odds_data, list_odds=[])
    probs = res.get("outcome_probabilities") or []

    def _nonzero_count(items) -> int:
        return sum(
            1
            for p in items or []
            if (p.get("home_prob") or 0)
            + (p.get("draw_prob") or 0)
            + (p.get("away_prob") or 0)
            > 0
        )

    # Быстрого пути не хватило (нужны полные H2H/история) — полная загрузка.
    if _nonzero_count(probs) < 8:
        try:
            info = MatchInfo(match_id=match_id)
            info.status = row["match_status"]
            info.start_ts = row["start_ts"]
            full = load_analysis_data(info, ms)
            if full.table_overall or full.form_overall:
                full.settings = ms
                full.match = info
                res_full = eng.run(full, odds_data, list_odds=[])
                probs_full = res_full.get("outcome_probabilities") or []
                if _nonzero_count(probs_full) > _nonzero_count(probs):
                    probs = probs_full
        except Exception as exc:  # noqa: BLE001
            print(f"    [!] полная загрузка: {exc}")

    return probs if probs else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Пересчёт нулевых outcome_probabilities"
    )
    parser.add_argument("--dry-run", action="store_true", help="только показать")
    parser.add_argument("--limit", type=int, default=0, help="ограничить число матчей")
    parser.add_argument(
        "--strategy",
        type=int,
        default=0,
        help="пересчитывать только если нули у этой стратегии (#1 или #4; 0 = обе)",
    )
    args = parser.parse_args()

    from settings import DeluxSettings

    cfg = DeluxSettings.from_env()

    conn = sqlite3.connect(str(get_database_path()), timeout=60)
    try:
        targets: list[str] = []
        for sid in ([args.strategy] if args.strategy else [1, 4]):
            for mid in _zero_matches(conn, sid):
                if mid not in targets:
                    targets.append(mid)
    finally:
        conn.close()

    print(f"Матчей с нулевыми вероятностями: {len(targets)}")
    if args.limit:
        targets = targets[: args.limit]
        print(f"Ограничено до: {len(targets)}")

    fixed = 0
    skipped = 0
    failed = 0
    started = time.time()

    for idx, mid in enumerate(targets, 1):
        try:
            probs = _recalc_one(mid, cfg)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"[{idx}/{len(targets)}] {mid}: ошибка — {exc}")
            continue

        if not probs:
            skipped += 1
            print(f"[{idx}/{len(targets)}] {mid}: пропуск (нет данных)")
            continue

        nonzero = sum(
            1
            for p in probs
            if (p.get("home_prob") or 0)
            + (p.get("draw_prob") or 0)
            + (p.get("away_prob") or 0)
            > 0
        )
        if args.dry_run:
            fixed += 1
            print(f"[{idx}/{len(targets)}] {mid}: [dry-run] ненулевых {nonzero}")
            continue

        if insert_outcome_probabilities_from_values(mid, probs):
            fixed += 1
            print(f"[{idx}/{len(targets)}] {mid}: записано, ненулевых {nonzero}")
        else:
            failed += 1
            print(f"[{idx}/{len(targets)}] {mid}: не записалось")

    elapsed = time.time() - started
    print()
    print(f"[+] Исправлено: {fixed}, пропущено: {skipped}, ошибок: {failed}")
    print(f"    время: {elapsed:.1f} c")
    if args.dry_run:
        print("    [dry-run] база не изменялась")
    return 0


if __name__ == "__main__":
    sys.exit(main())
