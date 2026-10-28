"""Снимок тура — вывод матчей с командами, датами, ID и доступными данными.

CLI:
    python round_snapshot.py list              # все матчи из БД
    python round_snapshot.py tr <sport> <tid>   # загрузить тур из tr_ feed
    python round_snapshot.py match <match_id>   # детальный снимок матча
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

FIELD_SEP = "÷"
ROW_SEP = "¬"


# ============================================================================
# ПАРСИНГ TR_ FEED
# ============================================================================

def fetch_feed(url: str) -> str:
    """Загрузить feed с Flashscore."""
    import urllib.request

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.flashscorekz.com/",
            "X-Fsign": "SW9D1eZo",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
        return ""


def parse_tr_feed(text: str) -> List[Dict[str, str]]:
    """Парсинг feed tr_ (матчи тура).

    Поля:
        AA — match_id
        AB — timestamp
        AE — home team
        AF — away team
        AT — score home
        AU — score away
        AG — half-time score home
        AH — half-time score away
        AR — status (1=live, 2=finished, 0=not started)
        AI — minute (for live)
        AN — round
        AP — period (1H/2H)
    """
    if not text:
        return []

    matches: List[Dict[str, str]] = []
    current: Dict[str, str] = {}

    for chunk in text.replace("~", ROW_SEP).split(ROW_SEP):
        chunk = chunk.strip()
        if not chunk:
            continue

        key, sep, value = chunk.partition(FIELD_SEP)
        if not sep:
            continue

        key, value = key.strip(), value.strip()

        if key == "AA":
            # Новый матч!
            if current and current.get("AA"):
                matches.append(dict(current))
            current = {}

        current[key] = value

    if current.get("AA"):
        matches.append(dict(current))

    return matches


def format_match_basic(m: Dict[str, str]) -> str:
    """Форматированный вывод одного матча (базовые поля)."""
    match_id = m.get("AA", "")
    ts = m.get("AB", "")
    try:
        match_date = datetime.fromtimestamp(int(ts)).strftime("%Y.%m.%d %H:%M")
    except (ValueError, OSError):
        match_date = "?"

    home = m.get("AE", "").replace("*", "")
    away = m.get("AF", "").replace("*", "")

    score_h = m.get("AT", "")
    score_a = m.get("AU", "")
    ht_h = m.get("AG", "")
    ht_a = m.get("AH", "")

    status = m.get("AR", "")
    minute = m.get("AI", "")
    round_num = m.get("AN", "")

    # Статус
    status_map = {"0": "Не начался", "1": "Live", "2": "Завершён"}
    status_str = status_map.get(status, status)

    score_str = f"{score_h}-{score_a}" if score_h and score_a else "?-?"
    ht_str = f" ({ht_h}-{ht_a})" if ht_h and ht_a else ""

    parts = [
        f"[{match_id}]",
        match_date,
        f"{home} vs {away}",
        f"{score_str}{ht_str}",
        status_str,
    ]
    if round_num:
        parts.append(f"Round {round_num}")
    if minute:
        parts.append(f"Min {minute}")

    return " | ".join(parts)


def format_match_detailed(m: Dict[str, str]) -> str:
    """Подробный вывод одного матча со всеми полями."""
    lines = []
    lines.append("=" * 80)

    # Основные данные
    match_id = m.get("AA", "")
    ts = m.get("AB", "")
    try:
        match_date = datetime.fromtimestamp(int(ts)).strftime("%Y.%m.%d %H:%M")
    except (ValueError, OSError):
        match_date = "?"

    home = m.get("AE", "").replace("*", "")
    away = m.get("AF", "").replace("*", "")

    score_h = m.get("AT", "")
    score_a = m.get("AU", "")
    ht_h = m.get("AG", "")
    ht_a = m.get("AH", "")

    status = m.get("AR", "")
    minute = m.get("AI", "")
    round_num = m.get("AN", "")
    period = m.get("AP", "")

    status_map = {"0": "Не начался", "1": "Live", "2": "Завершён"}
    status_str = status_map.get(status, status or "?")

    lines.append(f"Match ID:    {match_id}")
    lines.append(f"Дата:        {match_date}")
    lines.append(f"Раунд:       {round_num or '?'}")
    lines.append(f"Статус:      {status_str}")
    if minute:
        lines.append(f"Минута:      {minute}")
    if period:
        lines.append(f"Период:      {period}")
    lines.append("")
    lines.append("Команды:")
    lines.append(f"  Домашняя:  {home}")
    lines.append(f"  Гостевая:  {away}")
    lines.append("")
    lines.append("Счёт:")
    lines.append(f"  Основной:  {score_h or '?'}-{score_a or '?'}")
    if ht_h and ht_a:
        lines.append(f"  Half-time: {ht_h}-{ht_a}")

    # Все остальные поля
    extra = {k: v for k, v in m.items() if k not in (
        "AA", "AB", "AE", "AF", "AT", "AU", "AG", "AH", "AR", "AI", "AN", "AP"
    )}
    if extra:
        lines.append("")
        lines.append("Доп. поля:")
        for k, v in sorted(extra.items()):
            lines.append(f"  {k}: {v}")

    return "\n".join(lines)


# ============================================================================
# РАБОТА С БД
# ============================================================================

def get_db_connection() -> sqlite3.Connection:
    """Подключение к основной БД."""
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.environ.get("DATABASE_PATH", os.path.join(script_dir, "matches.db"))
    if not os.path.isabs(db_path):
        db_path = os.path.join(script_dir, db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def list_matches_from_db(limit: int = 50) -> List[Dict[str, Any]]:
    """Получить матчи из БД."""
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT
            m.match_id,
            m.match_date,
            m.score_home,
            m.score_away,
            m.match_status,
            th.name AS home_team,
            ta.name AS away_team,
            l.name AS league,
            c.name AS country
        FROM matches m
        JOIN teams th ON th.id = m.home_team_id
        JOIN teams ta ON ta.id = m.away_team_id
        LEFT JOIN leagues l ON l.id = m.league_id
        LEFT JOIN countries c ON c.id = l.country_id
        ORDER BY m.match_date DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()

    out = []
    for r in rows:
        out.append({
            "match_id": r["match_id"],
            "match_date": r["match_date"] or "?",
            "home": r["home_team"] or "?",
            "away": r["away_team"] or "?",
            "score_home": str(r["score_home"]) if r["score_home"] is not None else "",
            "score_away": str(r["score_away"]) if r["score_away"] is not None else "",
            "status": r["match_status"] or "Не начался",
            "league": f"{r['country']}: {r['league']}" if r["country"] and r["league"] else (r["league"] or "?"),
        })
    return out


def get_match_snapshot_from_db(match_id: str) -> Optional[Dict[str, Any]]:
    """Получить детальный снимок матча из БД."""
    conn = get_db_connection()
    row = conn.execute("""
        SELECT
            m.match_id,
            m.match_date,
            m.score_home,
            m.score_away,
            m.match_status,
            th.name AS home_team,
            ta.name AS away_team,
            l.name AS league,
            c.name AS country,
            ms.referee,
            ms.referee_country,
            ms.venue,
            ms.town,
            ms.capacity,
            ms.attendance,
            ms.standings_json,
            ms.form_json,
            ms.h2h_json,
            ms.team_matches_json,
            ms.weather_json,
            ms.distance,
            ms.home_venue,
            ms.away_venue
        FROM matches m
        JOIN teams th ON th.id = m.home_team_id
        JOIN teams ta ON ta.id = m.away_team_id
        LEFT JOIN leagues l ON l.id = m.league_id
        LEFT JOIN countries c ON c.id = l.country_id
        LEFT JOIN match_snapshot ms ON ms.match_id = m.match_id
        WHERE m.match_id = ?
    """, (match_id,)).fetchone()
    conn.close()

    if not row:
        return None

    out: Dict[str, Any] = {}
    for key in row.keys():
        val = row[key]
        if isinstance(val, str) and val.startswith("{"):
            try:
                val = json.loads(val)
            except json.JSONDecodeError:
                pass
        out[key] = val

    return out


def format_db_match(m: Dict[str, Any]) -> str:
    """Форматированный вывод матча из БД."""
    score_str = f"{m['score_home']}-{m['score_away']}" if m['score_home'] and m['score_away'] else "?-?"
    return (
        f"[{m['match_id']}] {m['match_date']} | "
        f"{m['home']} vs {m['away']} | "
        f"{score_str} | "
        f"{m['status']} | "
        f"{m['league']}"
    )


def format_db_match_detailed(m: Dict[str, Any]) -> str:
    """Подробный вывод матча из БД."""
    lines = []
    lines.append("=" * 80)
    lines.append(f"Match ID:      {m.get('match_id', '?')}")
    lines.append(f"Дата:          {m.get('match_date', '?')}")
    lines.append(f"Лига:          {m.get('league', '?')}")
    lines.append(f"Статус:        {m.get('match_status', m.get('status', '?'))}")
    lines.append("")
    lines.append("Команды:")
    lines.append(f"  Домашняя:    {m.get('home', m.get('home_team', '?'))}")
    lines.append(f"  Гостевая:    {m.get('away', m.get('away_team', '?'))}")
    lines.append("")
    lines.append("Счёт:")
    sh = m.get('score_home')
    sa = m.get('score_away')
    lines.append(f"  Основной:    {sh if sh is not None else '?'}-{sa if sa is not None else '?'}")

    # Данные из match_snapshot
    for field, label in [
        ("referee", "Судья"),
        ("referee_country", "Страна судьи"),
        ("venue", "Стадион"),
        ("town", "Город"),
        ("capacity", "Вместимость"),
        ("attendance", "Зрители"),
        ("distance", "Расстояние (км)"),
    ]:
        val = m.get(field)
        if val:
            lines.append(f"{label}: {val}")

    # JSON поля
    for field, label in [
        ("standings_json", "Таблица лиги"),
        ("form_json", "Форма команд"),
        ("h2h_json", "Личные встречи"),
        ("team_matches_json", "Матчи команд"),
        ("weather_json", "Погода"),
    ]:
        val = m.get(field)
        if val and isinstance(val, dict) and val:
            lines.append("")
            lines.append(f"{label}:")
            lines.append(json.dumps(val, ensure_ascii=False, indent=2))

    return "\n".join(lines)


# ============================================================================
# CLI
# ============================================================================

def cmd_list(args: argparse.Namespace) -> None:
    """Список матчей из БД."""
    matches = list_matches_from_db(args.limit)
    if not matches:
        print("[INFO] Матчей не найдено")
        return

    print(f"\nМатчи ({len(matches)}):")
    print("-" * 80)
    for i, m in enumerate(matches, 1):
        print(f"  [{i:>3}] {format_db_match(m)}")

    if args.detail:
        print("\n" + "=" * 80)
        print("ДЕТАЛЬНЫЙ ПРОСМОТР (первые 5):")
        print("=" * 80)
        for m in matches[:5]:
            print(format_db_match_detailed(m))


def cmd_tr(args: argparse.Namespace) -> None:
    """Загрузить тур из tr_ feed."""
    sport = args.sport
    tid = args.tid

    print(f"\nЗагрузка тура: sport={sport}, tournament={tid}")
    print("=" * 80)

    # Загружаем все страницы (0-4)
    all_matches = []
    for page in range(5):
        url = f"https://46.flashscore.ninja/46/x/feed/tr_{sport}_{tid}_{page}_1_ru-kz_1"
        text = fetch_feed(url)

        if not text or len(text) < 100:
            print(f"[SKIP] Страница {page}")
            continue

        matches = parse_tr_feed(text)
        print(f"[OK] Страница {page}: {len(matches)} матчей")
        all_matches.extend(matches)

    if not all_matches:
        print("[ERROR] Матчей не загружено")
        return

    print(f"\nВсего: {len(all_matches)} матчей")
    print("-" * 80)

    # Базовый вывод
    for i, m in enumerate(all_matches, 1):
        print(f"  [{i:>3}] {format_match_basic(m)}")

    if args.detail:
        print("\n" + "=" * 80)
        print("ДЕТАЛЬНЫЙ ПРОСМОТР (первые 5):")
        print("=" * 80)
        for m in all_matches[:5]:
            print(format_match_detailed(m))


def cmd_match(args: argparse.Namespace) -> None:
    """Детальный снимок одного матча."""
    snap = get_match_snapshot_from_db(args.match_id)
    if not snap:
        print(f"[ERROR] Матч {args.match_id} не найден")
        return

    print(format_db_match_detailed(snap))


def main():
    parser = argparse.ArgumentParser(description="Снимок тура")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="Список матчей из БД")
    p_list.add_argument("--limit", type=int, default=50, help="Количество матчей")
    p_list.add_argument("--detail", action="store_true", help="Детальный просмотр")

    p_tr = sub.add_parser("tr", help="Загрузить тур из tr_ feed")
    p_tr.add_argument("sport", type=int, help="ID спорта")
    p_tr.add_argument("tid", help="ID турнира")
    p_tr.add_argument("--detail", action="store_true", help="Детальный просмотр")

    p_match = sub.add_parser("match", help="Детальный снимок матча")
    p_match.add_argument("match_id", help="ID матча")

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(args)
    elif args.command == "tr":
        cmd_tr(args)
    elif args.command == "match":
        cmd_match(args)


if __name__ == "__main__":
    main()
