"""Полный архив старого матча в рабочую БД matches.db.

По match_id делает три вещи:
1. Разрешает матч из tr_ фида турнира (команды, ключи, лига, счёт, дата).
2. Записывает матч в matches.db (как обычный, is_archived=1).
3. Восстанавливает таблицу лиги на момент матча (overall/home/away) и пишет
   в match_snapshot.standings_json.
4. Подтягивает последние N игр обеих команд (pr_ фид) как архивные матчи.

Пример:
    py archive_old_match.py --match-id WzuV5eoq --tournament-key dYlOSQOD --season-id 165
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from flashscore_feed import fetch_feed, clean_team_name
from team_history import parse_pr_feed, fetch_team_matches_before, format_match_date

DEFAULT_DB = "matches.db"

# Кэш известных (tournament_template_id -> season_id) по годам.
# Пополняется вручную/автоматически, чтобы не прощупывать сеть каждый раз.
_SEASON_CACHE_PATH = Path(__file__).parent / "research" / "season_cache.json"

# Известные пары (замерено): АПЛ Англии dYlOSQOD.
_SEASON_KNOWN = {
    "dYlOSQOD": {
        "2014/15": "160",
        "2015/16": "165",
        "2016/17": "167",
        "2018/19": "169",
        "2025/26": "190",
    },
}


def _load_season_cache() -> Dict[str, Dict[str, str]]:
    cache = dict(_SEASON_KNOWN)
    try:
        if _SEASON_CACHE_PATH.exists():
            data = json.loads(_SEASON_CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for key, val in data.items():
                    if isinstance(val, dict):
                        cache.setdefault(key, {}).update(val)
    except (OSError, json.JSONDecodeError):
        pass
    return cache


def _save_season_cache(cache: Dict[str, Dict[str, str]]) -> None:
    try:
        _SEASON_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SEASON_CACHE_PATH.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:  # noqa: BLE001
        print(f"[!] не удалось сохранить season_cache: {exc}")


def resolve_season_id(
    tournament_template_id: str,
    sport: int,
    country: int,
    kickoff_ts: int,
    match_id: str = "",
) -> Optional[str]:
    """Найти числовой season_id через страницы Flashscore.

    Переадресация на tournament_resolver.resolve_season_id (pageinfo ->
    season_list -> results seasonId). Параметры sport/country/kickoff_ts
    сохранены для обратной совместимости сигнатуры.
    """
    from tournament_resolver import resolve_season_id as _resolve
    _ = tournament_template_id, sport, country, kickoff_ts
    return _resolve(match_id=match_id)


# ----------------------------------------------------------------------------- tr_ feed
def tr_feed_url(sport: int, country: int, tournament_key: str, season_id: str, page: int) -> str:
    return (
        f"https://46.flashscore.ninja/46/x/feed/"
        f"tr_{sport}_{country}_{tournament_key}_{season_id}_{page}_1_ru-kz_1"
    )


def fetch_tournament_matches(
    sport: int, country: int, tournament_key: str, season_id: str, max_pages: int = 40
) -> List[Dict[str, Any]]:
    """Все матчи турнира из tr_ feed (хронологически, без дублей).

    max_pages=40: сезон из 380 матчей — это ~19 страниц по 20 игр; при
    меньшем лимите часть сезона терялась и таблица на момент матча
    получалась неполной.

    Устойчиво к сбоям сети: неудачные страницы пропускаются с предупреждением.
    """
    collected: Dict[str, Dict[str, Any]] = {}
    for page in range(max_pages):
        url = tr_feed_url(sport, country, tournament_key, season_id, page)
        try:
            text = fetch_feed(url, retries=3, timeout=40)
        except Exception as exc:  # noqa: BLE001
            print(f"[!] страница {page} не загружена: {exc}")
            continue
        if not text or len(text) < 100:
            continue
        parsed = parse_pr_feed(text)
        for m in parsed:
            collected.setdefault(m["match_id"], m)
    return sorted(collected.values(), key=lambda m: (m["kickoff_ts"], m["match_id"]))


# --------------------------------------------------------------------- таблица
def _new_stats() -> Dict[str, int]:
    return {"played": 0, "wins": 0, "draws": 0, "losses": 0, "scored": 0, "conceded": 0, "points": 0}


def _rank(stats: Dict[str, Dict[str, int]]) -> List[Dict[str, Any]]:
    items = sorted(
        stats.items(),
        key=lambda kv: (
            -kv[1]["points"],
            -(kv[1]["scored"] - kv[1]["conceded"]),
            -kv[1]["scored"],
            kv[0],
        ),
    )
    return [{"team": name, "rank": rank, **s} for rank, (name, s) in enumerate(items, 1)]


def _add_game(stats: Dict[str, Dict[str, int]], team: str, gf: int, ga: int) -> None:
    s = stats[team]
    s["played"] += 1
    s["scored"] += gf
    s["conceded"] += ga
    if gf > ga:
        s["wins"] += 1
        s["points"] += 3
    elif gf < ga:
        s["losses"] += 1
    else:
        s["draws"] += 1
        s["points"] += 1


def reconstruct_all_standings(
    matches: List[Dict[str, Any]],
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """Таблицы на момент КАЖДОГО матча за один линейный проход.

    Возвращает {match_id: {overall, home, away}}.

    В отличие от reconstruct_standings_before (пересчёт с нуля для каждого
    kickoff, O(n²)), здесь состояние накапливается: матчи обходятся по
    возрастанию времени, и перед каждым снимается текущая таблица.
    Для сезона из 380 матчей это ~380 шагов вместо 380×380.
    """
    ordered = sorted(
        (m for m in (matches or []) if m.get("kickoff_ts")),
        key=lambda m: (m["kickoff_ts"], m.get("match_id", "")),
    )
    teams = {m["home_name"] for m in ordered} | {m["away_name"] for m in ordered}
    stats = {tt: {n: _new_stats() for n in teams} for tt in ("overall", "home", "away")}

    out: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    # Матчи с одинаковым kickoff_ts не должны влиять друг на друга —
    # поэтому сначала снимаем таблицу для всей группы, затем применяем.
    index = 0
    while index < len(ordered):
        ts = ordered[index]["kickoff_ts"]
        group_end = index
        while group_end < len(ordered) and ordered[group_end]["kickoff_ts"] == ts:
            group_end += 1

        snapshot = {tt: _rank(stats[tt]) for tt in ("overall", "home", "away")}
        for m in ordered[index:group_end]:
            mid = m.get("match_id")
            if mid:
                out[mid] = snapshot

        for m in ordered[index:group_end]:
            sh = m["home_score"] or 0
            sa = m["away_score"] or 0
            _add_game(stats["overall"], m["home_name"], sh, sa)
            _add_game(stats["overall"], m["away_name"], sa, sh)
            _add_game(stats["home"], m["home_name"], sh, sa)
            _add_game(stats["away"], m["away_name"], sa, sh)

        index = group_end

    return out


def reconstruct_standings_before(
    matches: List[Dict[str, Any]], kickoff_ts: int
) -> Dict[str, List[Dict[str, Any]]]:
    """Таблицы (overall/home/away) по матчам строго ДО kickoff_ts."""
    teams = {m["home_name"] for m in matches} | {m["away_name"] for m in matches}
    stats = {tt: {n: _new_stats() for n in teams} for tt in ("overall", "home", "away")}

    for m in matches:
        if m["kickoff_ts"] >= kickoff_ts:
            continue
        sh = m["home_score"] or 0
        sa = m["away_score"] or 0
        _add_game(stats["overall"], m["home_name"], sh, sa)
        _add_game(stats["overall"], m["away_name"], sa, sh)
        _add_game(stats["home"], m["home_name"], sh, sa)
        _add_game(stats["away"], m["away_name"], sa, sh)

    return {tt: _rank(stats[tt]) for tt in ("overall", "home", "away")}


def _season_of_year(tournament_key: str, sport: int, country: int, year: int) -> Optional[str]:
    """Подобрать числовой season_id по году матча перебором соседних id.

    Flashscore нумерует сезоны непоследовательно, поэтому прощупываем
    диапазон season_id вокруг оценённого значения и берём тот, чей tr_ фид
    содержит матчи нужного года.
    """
    from datetime import datetime
    # эвристика: season_id примерно растёт с годом; 165~2016, 190~2026
    base = 150 + (year - 2012) * 3  # грубая оценка
    for season in range(max(0, base - 15), base + 20):
        url = tr_feed_url(sport, country, tournament_key, str(season), 0)
        try:
            text = fetch_feed(url, retries=1, timeout=20)
        except Exception:  # noqa: BLE001
            continue
        if not text or len(text) < 100:
            continue
        years = set()
        for m in parse_pr_feed(text):
            ts = m.get("kickoff_ts") or 0
            if ts:
                try:
                    years.add(datetime.fromtimestamp(ts).year)
                except (ValueError, OSError):
                    pass
        if year in years:
            return str(season)
    return None


def resolve_season_id(
    tournament_template_id: str,
    sport: int,
    country: int,
    kickoff_ts: int,
    match_id: str = "",
) -> Optional[str]:
    """Найти числовой season_id турнира, где играл целевой матч.

    season_id недоступен из страницы матча и dc_ фида, поэтому прощупываем
    tr_ фиды соседних сезонов. Приоритет — точное совпадение match_id;
    fallback — сезон, чей год матчей совпадает с годом кик-оффа.

    Перебор устойчив к таймаутам (пропускаем недоступные страницы) и
    идёт от сезона «на 2 года раньше» до «на 3 года позже» пивота.
    """
    from datetime import datetime
    if not tournament_template_id:
        return None

    year = 0
    if kickoff_ts:
        try:
            year = datetime.fromtimestamp(kickoff_ts).year
        except (ValueError, OSError, OverflowError):
            year = 0

    # Пивотная оценка. Календарные соотношения (замерено):
    #   season 160 -> матчи 2014/15 (год 2015), 165 -> 2015/16, 190 -> 2026
    # Для августа-декабря год матча относится к сезону, начавшемуся в этом году,
    # т.е. season_id порядка "150 + 3*(год-2012) + 6". Перебираем широко.
    base = 150 + (year - 2012) * 3 if year else 165

    best_by_year = None
    for season in range(max(0, base - 8), base + 14):
        url = tr_feed_url(sport, country, tournament_template_id, str(season), 0)
        try:
            text = fetch_feed(url, retries=2, timeout=25)
        except Exception:  # noqa: BLE001
            continue
        if not text or len(text) < 100:
            continue

        parsed = parse_pr_feed(text)
        years = set()
        for m in parsed:
            if match_id and m.get("match_id") == match_id:
                return str(season)  # точное попадание — сразу ответ
            ts = m.get("kickoff_ts") or 0
            if ts:
                try:
                    years.add(datetime.fromtimestamp(ts).year)
                except (ValueError, OSError):
                    pass
        if year and year in years:
            best_by_year = str(season)

    return best_by_year


# --------------------------------------------------------------------- запись
def _write_all(
    db_path: str,
    target: Dict[str, Any],
    standings: Dict[str, List[Dict[str, Any]]],
    histories: List[Dict[str, Any]],
    sport: int,
    limit: int,
) -> None:
    """Записать матч + таблицу + историю команд в рабочую БД (одна транзакция)."""
    from db import (
        database_path,
        create_database,
        get_db_connection,
        parse_league,
        insert_or_get_country,
        insert_or_get_league,
        insert_or_get_team,
    )

    with database_path(db_path):
        create_database()
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # --- матч ---
            country_name, league_name = parse_league(target.get("competition") or "")
            country_id = insert_or_get_country(cursor, country_name)
            league_id = insert_or_get_league(cursor, league_name, country_id)
            home_id = insert_or_get_team(cursor, clean_team_name(target["home_name"]))
            away_id = insert_or_get_team(cursor, clean_team_name(target["away_name"]))

            cursor.execute(
                """
                INSERT OR REPLACE INTO matches
                (match_id, match_date, start_ts, league_id, home_team_id, away_team_id,
                 match_status, score_home, score_away, sport, is_archived)
                VALUES (?, ?, ?, ?, ?, ?, 'Завершен', ?, ?, ?, 1)
                """,
                (
                    target["match_id"],
                    format_match_date(target["kickoff_ts"]),
                    target["kickoff_ts"],
                    league_id, home_id, away_id,
                    target.get("home_score") or 0, target.get("away_score") or 0,
                    sport,
                ),
            )

            # --- таблица ---
            cursor.execute(
                """
                INSERT INTO match_snapshot (match_id, standings_json, fetched_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(match_id) DO UPDATE SET
                    standings_json = excluded.standings_json,
                    fetched_at = excluded.fetched_at
                """,
                (target["match_id"], json.dumps(standings, ensure_ascii=False)),
            )

            # --- история команд (архивные матчи) ---
            for m in histories:
                if not m.get("match_id") or not m.get("home_name") or not m.get("away_name"):
                    continue
                c, l = parse_league(m.get("competition") or "")
                cid = insert_or_get_country(cursor, c)
                lid = insert_or_get_league(cursor, l, cid)
                hid = insert_or_get_team(cursor, clean_team_name(m["home_name"]))
                aid = insert_or_get_team(cursor, clean_team_name(m["away_name"]))
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO matches
                    (match_id, match_date, start_ts, league_id, home_team_id, away_team_id,
                     match_status, score_home, score_away, sport, is_archived)
                    VALUES (?, ?, ?, ?, ?, ?, 'Завершен', ?, ?, ?, 1)
                    """,
                    (
                        m["match_id"],
                        format_match_date(m["kickoff_ts"]),
                        m["kickoff_ts"], lid, hid, aid,
                        m["home_score"] or 0, m["away_score"] or 0,
                        sport,
                    ),
                )

            conn.commit()

    # сколько записали истории
    history_ids = {m["match_id"] for m in histories}
    return len(history_ids)


# --------------------------------------------------------------------- CLI
def main() -> None:
    parser = argparse.ArgumentParser(description="Полный архив старого матча в рабочую БД")
    parser.add_argument("--match-id", required=True, help="Flashscore id матча (напр. WzuV5eoq)")
    parser.add_argument("--sport", type=int, default=1, help="Вид спорта")
    parser.add_argument("--country-id", type=int, default=198, help="ID страны (198=Англия)")
    parser.add_argument("--tournament-key", required=True, help="Ключ турнира в tr_ фиде (напр. dYlOSQOD)")
    parser.add_argument("--season-id", required=True, help="ID сезона (напр. 165)")
    parser.add_argument("--limit", type=int, default=40, help="Сколько последних матчей на команду")
    parser.add_argument("--db", default=DEFAULT_DB, help="Путь к рабочей БД (по умолчанию matches.db)")
    args = parser.parse_args()

    # 1) матчи турнира + целевой матч
    matches = fetch_tournament_matches(args.sport, args.country_id, args.tournament_key, args.season_id)
    target = next((m for m in matches if m["match_id"] == args.match_id), None)
    if not target:
        raise SystemExit(f"[!] Матч {args.match_id} не найден в турнире {args.tournament_key}/{args.season_id}")

    print(f"матч: {target['home_name']} {target['home_score']}:{target['away_score']} {target['away_name']} "
          f"@ {format_match_date(target['kickoff_ts'])} ({target['competition']})")

    # 2) таблица на момент матча
    standings = reconstruct_standings_before(matches, target["kickoff_ts"])
    print(f"таблица: overall={len(standings['overall'])} home={len(standings['home'])} away={len(standings['away'])} команд")

    # 3) история команд: матчи турнира, сыгранные строго ДО целевого (реконструкция)
    histories: List[Dict[str, Any]] = []
    for name in (target["home_name"], target["away_name"]):
        team_matches = [
            m for m in matches
            if (m["home_name"] == name or m["away_name"] == name)
            and m["kickoff_ts"] < target["kickoff_ts"]
        ]
        team_matches = team_matches[-args.limit:]
        histories.extend(team_matches)
        print(f"история {name} (турнир): {len(team_matches)} матчей до игры")

    # 4) перенос прошедших матчей команд (pr_ feed, все турниры, до целевого).
    # Используем fetch_team_matches_before — пагинирует ВГЛУБЬ по страницам,
    # пока не наберёт limit матчей строго до целевого (доводя до 40).
    for key, name in ((target["home_key"], target["home_name"]), (target["away_key"], target["away_name"])):
        if not key:
            continue
        pr_matches = fetch_team_matches_before(
            key, target["kickoff_ts"],
            country=args.country_id, sport=args.sport, limit=args.limit
        )
        histories.extend(pr_matches)
        print(f"перенос {name} (pr_): {len(pr_matches)} матчей до игры")

    # 4) запись в рабочую БД
    _write_all(args.db, target, standings, histories, args.sport, args.limit)
    print(f"\n[OK] Архив записан в {args.db}: матч {args.match_id} + таблица + {len(histories)} архивных матчей")


if __name__ == "__main__":
    main()
