"""Тестовая БД для парсинга Flashscore API.

Задача:
1. Создать тестовую БД с 2 матчами
2. Спарсить турнир АПЛ 2016 через feed API
3. Восстановить таблицу лиги (кто и когда получал очки)
4. Сделать снимок таблицы для каждого матча
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ============================================================================
# ТЕСТОВАЯ БД
# ============================================================================

TEST_DB_PATH = Path(__file__).parent / "test_flashscore.db"


def create_test_db() -> sqlite3.Connection:
    """Создать тестовую БД с базовыми таблицами."""
    conn = sqlite3.connect(str(TEST_DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()
    
    # Таблица турниров
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tournaments (
            tournament_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            sport INTEGER DEFAULT 1,
            country TEXT,
            season TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    # Таблица команд
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            tournament_id TEXT,
            FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id)
        )
    """)
    
    # Таблица матчей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            match_id TEXT PRIMARY KEY,
            tournament_id TEXT,
            match_date TEXT NOT NULL,
            round TEXT,
            home_team_id INTEGER,
            away_team_id INTEGER,
            score_home INTEGER,
            score_away INTEGER,
            match_status TEXT DEFAULT 'Не начался',
            FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id),
            FOREIGN KEY (home_team_id) REFERENCES teams(id),
            FOREIGN KEY (away_team_id) REFERENCES teams(id)
        )
    """)
    
    # Таблица таблицы лиги (снимок на момент матча)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS standings_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT NOT NULL,
            tournament_id TEXT NOT NULL,
            team_name TEXT NOT NULL,
            rank INTEGER,
            played INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            scored INTEGER DEFAULT 0,
            conceded INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            snapshot_date TEXT NOT NULL,
            table_type TEXT NOT NULL DEFAULT 'overall',
            FOREIGN KEY (match_id) REFERENCES matches(match_id),
            FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id)
        )
    """)
    
    # Миграция: добавить table_type, если таблица создана без него (старые БД)
    if "table_type" not in {row[1] for row in cursor.execute("PRAGMA table_info(standings_snapshot)")}:
        cursor.execute(
            "ALTER TABLE standings_snapshot ADD COLUMN table_type TEXT NOT NULL DEFAULT 'overall'"
        )
    
    # Таблица сырых feed данных
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feed_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT,
            feed_type TEXT NOT NULL,  -- 'tx', 'to', 'df_hh', 'pr'
            feed_url TEXT,
            raw_data TEXT,
            parsed_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    # Предыдущие матчи команды (feed pr_) — реконструкция формы
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_previous_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_key TEXT NOT NULL,
            team_name TEXT,
            match_id TEXT NOT NULL,
            kickoff_ts INTEGER,
            match_date TEXT,
            competition TEXT,
            home_key TEXT,
            home_name TEXT,
            away_key TEXT,
            away_name TEXT,
            home_score INTEGER,
            away_score INTEGER,
            is_home INTEGER,
            UNIQUE(team_key, match_id)
        )
    """)
    
    conn.commit()
    return conn


# ============================================================================
# ПАРСИНГ FLASHSCORE FEED
# ============================================================================

def fetch_feed(url: str) -> str:
    """Загрузить feed с Flashscore."""
    import urllib.request
    
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.flashscore.com/",
            "X-Fsign": "SW9D1eZo",
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
        return ""


def parse_tr_feed(text: str) -> List[Dict[str, Any]]:
    """Парсинг feed tr_ (матчи тура).
    
    URL: tr_{sport}_{tournament_id}_{page}_{lang}
    Матчи идут по убыванию (38 -> 1)
    
    Структура:
    - AA÷{match_id} — начало матча (80 матчей на страницах 1-4, 1 на странице 0)
    - AB÷{timestamp} — время матча
    - AE÷{home_team} — домашняя команда
    - AF÷{away_team} — гостевая команда
    - AT/AU — счёт
    """
    from flashscore_feed import ROW_SEP, FIELD_SEP
    
    if not text:
        return []
    
    matches = []
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


def parse_to_feed(text: str, table_index: int) -> List[Dict[str, Any]]:
    """Парсинг feed to_ (таблица лиги).
    
    table_index: 1=overall, 2=home, 3=away, 5=form_overall, ...
    """
    if not text:
        return []
    
    rows = []
    temper = False
    temper_value = "0" if table_index in (1, 2, 3) else "0"
    
    for block in text.split("¬~"):
        parts = block.split("¬")
        if not parts:
            continue
        
        head = parts[0].split("÷")
        if len(head) < 2:
            continue
        
        index_name, index_value = head[0], head[1]
        
        if index_name == "ETI":
            temper = index_value == temper_value
            continue
        
        if index_name != "TR" or not temper:
            continue
        
        game: Dict[str, str] = {}
        for part in parts:
            p = part.split("÷")
            if len(p) < 2:
                continue
            key, val = p[0], p[1]
            if key == "TR":
                game["rank"] = val
            elif key == "TN":
                game["team"] = val
            elif key == "TM":
                game["played"] = val
            elif key in ("TWR", "OUO"):
                game["wins"] = val
            elif key in ("TDR", "OUU"):
                game["draws"] = val
            elif key == "TLR" and "losses" not in game:
                game["losses"] = val
            elif key == "TG":
                scored, conceded = (val.split(":") + ["0", "0"])[:2]
                if "scored" not in game:
                    game["scored"] = scored
                game["conceded"] = conceded
            elif key == "TP":
                game["points"] = val
        
        if game.get("team"):
            rows.append(game)
    
    return rows


# ============================================================================
# ОСНОВНАЯ ЛОГИКА
# ============================================================================

def test_parse_tr_feed():
    """Тест парсинга tr_ feed (матчи тура)."""
    print("\n" + "="*60)
    print("TEST 1: Парсинг tr_ feed (матчи тура)")
    print("="*60)
    
    # Загружаем все страницы (0-4 = 38-1 туры)
    pages = ["0", "1", "2", "3", "4"]
    all_matches = []
    
    for page in pages:
        url = f"https://46.flashscore.ninja/46/x/feed/tr_1_198_dYlOSQOD_165_{page}_1_ru-kz_1"
        text = fetch_feed(url)
        
        if not text or len(text) < 100:
            print(f"[SKIP] Page {page}")
            continue
        
        matches = parse_tr_feed(text)
        print(f"[OK] Page {page}: {len(matches)} matches")
        all_matches.extend(matches)
    
    print(f"\n[INFO] Total: {len(all_matches)} matches")
    
    # Показываем первые 5
    for i, m in enumerate(all_matches[:5], 1):
        home = m.get("AE", "").replace("*", "")
        away = m.get("AF", "").replace("*", "")
        score_h = m.get("AT", "?")
        score_a = m.get("AU", "?")
        print(f"  [{i}] {home} vs {away} | Score: {score_h}-{score_a}")
    
    return all_matches


def test_parse_to_feed():
    """Тест парсинга to_ feed (таблица лиги)."""
    print("\n" + "="*60)
    print("TEST 2: Парсинг to_ feed (таблица лиги)")
    print("="*60)
    
    url = "https://46.flashscore.ninja/46/x/feed/to_OhnzLqf7_faBBhyuM_1"
    text = fetch_feed(url)
    
    if not text:
        print("[ERROR] Не удалось загрузить feed")
        return None, None
    
    # Сохраняем сырые данные
    conn = create_test_db()
    conn.execute(
        "INSERT INTO feed_snapshots (feed_type, feed_url, raw_data) VALUES (?, ?, ?)",
        ("to_overall", url, text)
    )
    conn.commit()
    
    # Парсим таблицу
    table = parse_to_feed(text, table_index=1)
    print(f"\n[INFO] Найдено {len(table)} команд в таблице")
    
    # Показываем топ-5
    print("\n  Топ-5 команд:")
    print(f"  {'Rank':<6} {'Team':<25} {'P':<4} {'W':<4} {'D':<4} {'L':<4} {'GD':<8} {'Pts':<6}")
    print("  " + "-"*62)
    for i, row in enumerate(table[:5], 1):
        played = row.get("played", "0")
        wins = row.get("wins", "0")
        draws = row.get("draws", "0")
        losses = row.get("losses", "0")
        scored = row.get("scored", "0")
        conceded = row.get("conceded", "0")
        points = row.get("points", "0")
        gd = f"{int(scored) - int(conceded):+d}" if scored and conceded else "0"
        
        print(f"  {i:<6} {row.get('team', ''):<25} {played:<4} {wins:<4} {draws:<4} {losses:<4} {gd:<8} {points:<6}")
    
    return text, table


def save_match_to_db(conn: sqlite3.Connection, match_data: Dict[str, Any], tournament_id: str) -> Optional[int]:
    """Сохранить матч в БД и вернуть team_id."""
    cursor = conn.cursor()
    
    # Парсим дату (AB — служебный флаг, реальный таймстамп в AD/ADE)
    date_ts = match_data.get("AD", "") or match_data.get("ADE", "")
    if date_ts:
        try:
            match_date = datetime.fromtimestamp(int(date_ts)).strftime("%Y.%m.%d %H:%M")
        except (ValueError, OSError):
            match_date = datetime.now().strftime("%Y.%m.%d %H:%M")
    else:
        match_date = datetime.now().strftime("%Y.%m.%d %H:%M")
    
    # Команды
    home_name = match_data.get("AE", "").replace("*", "")
    away_name = match_data.get("AF", "").replace("*", "")
    
    if not home_name or not away_name:
        return None
    
    # Добавляем команды
    cursor.execute("INSERT OR IGNORE INTO teams (name, tournament_id) VALUES (?, ?)",
                   (home_name, tournament_id))
    cursor.execute("INSERT OR IGNORE INTO teams (name, tournament_id) VALUES (?, ?)",
                   (away_name, tournament_id))
    
    home_id = cursor.execute("SELECT id FROM teams WHERE name = ?", (home_name,)).fetchone()[0]
    away_id = cursor.execute("SELECT id FROM teams WHERE name = ?", (away_name,)).fetchone()[0]
    
    # Добавляем матч
    match_id = match_data.get("AA", f"test_{home_name}_{away_name}")
    score_home = match_data.get("AT") or match_data.get("AG") or "0"
    score_away = match_data.get("AU") or match_data.get("AH") or "0"
    
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO matches 
            (match_id, tournament_id, match_date, home_team_id, away_team_id, 
             score_home, score_away, match_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            match_id, tournament_id, match_date,
            home_id, away_id,
            int(float(score_home)), int(float(score_away)),
            "Завершен" if score_home and score_away else "Не начался"
        ))
    except (ValueError, TypeError):
        cursor.execute("""
            INSERT OR REPLACE INTO matches 
            (match_id, tournament_id, match_date, home_team_id, away_team_id,
             match_status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            match_id, tournament_id, match_date,
            home_id, away_id,
            "Не начался"
        ))
    
    conn.commit()
    return match_id


def save_standings_snapshot(
    conn: sqlite3.Connection,
    match_id: str,
    tournament_id: str,
    table: List[Dict[str, Any]],
    snapshot_date: str,
) -> int:
    """Сохранить снимок таблицы лиги (из to_ feed) для матча.

    Возвращает число сохранённых команд.
    """
    def _int(key: str) -> int:
        try:
            return int(float(row.get(key) or 0))
        except (ValueError, TypeError):
            return 0

    saved = 0
    for row in table:
        team = (row.get("team") or "").strip()
        if not team:
            continue
        conn.execute(
            """
            INSERT INTO standings_snapshot
            (match_id, tournament_id, team_name, rank, played, wins, draws, losses,
             scored, conceded, points, snapshot_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                tournament_id,
                team,
                _int("rank"),
                _int("played"),
                _int("wins"),
                _int("draws"),
                _int("losses"),
                _int("scored"),
                _int("conceded"),
                _int("points"),
                snapshot_date,
            ),
        )
        saved += 1
    conn.commit()
    return saved


def restore_standings_from_matches(conn: sqlite3.Connection, tournament_id: str) -> int:
    """Восстанавливает таблицу лиги по матчам.
    
    Для каждого матча рассчитывает очки:
    - Победа: 3 очка
    - Ничья: 1 очко
    - Поражение: 0 очков
    
    Сохраняет снимок таблицы после каждого матча.
    
    Returns: количество сохранённых снимков
    """
    print("\n[RESTORE] Restoring standings from matches...")
    
    # Получаем все матчи по дате
    matches = conn.execute("""
        SELECT m.match_id, m.match_date, m.score_home, m.score_away,
               th.name AS home_team, ta.name AS away_team
        FROM matches m
        JOIN teams th ON th.id = m.home_team_id
        JOIN teams ta ON ta.id = m.away_team_id
        WHERE m.tournament_id = ?
        ORDER BY m.match_date ASC
    """, (tournament_id,)).fetchall()
    
    if not matches:
        print("[RESTORE] No matches found")
        return 0
    
    print(f"[RESTORE] Found {len(matches)} matches")
    
    # Счётчик для каждой команды
    team_stats: Dict[str, Dict[str, int]] = {}
    
    snapshots_saved = 0
    
    for i, m in enumerate(matches, 1):
        m_dict = dict(m)
        match_id = m_dict['match_id']
        match_date = m_dict['match_date']
        home_team = m_dict['home_team']
        away_team = m_dict['away_team']
        score_home = m_dict['score_home'] or 0
        score_away = m_dict['score_away'] or 0
        
        # Инициализируем команды если нет
        for team in [home_team, away_team]:
            if team not in team_stats:
                team_stats[team] = {
                    "played": 0, "wins": 0, "draws": 0, "losses": 0,
                    "scored": 0, "conceded": 0, "points": 0
                }
        
        # Обновляем статистику
        home = team_stats[home_team]
        away = team_stats[away_team]
        
        home["played"] += 1
        away["played"] += 1
        home["scored"] += score_home
        home["conceded"] += score_away
        away["scored"] += score_away
        away["conceded"] += score_home
        
        if score_home > score_away:
            home["wins"] += 1
            home["points"] += 3
            away["losses"] += 1
        elif score_home < score_away:
            away["wins"] += 1
            away["points"] += 3
            home["losses"] += 1
        else:
            home["draws"] += 1
            away["draws"] += 1
            home["points"] += 1
            away["points"] += 1
        
        # Сортируем по очкам, затем по разнице мячей
        sorted_teams = sorted(
            team_stats.items(),
            key=lambda x: (x[1]["points"], x[1]["scored"] - x[1]["conceded"], -x[1]["played"]),
            reverse=True
        )
        
        # Сохраняем снимок таблицы (каждый 5-й матч для экономии места)
        if i % 5 == 0 or i == len(matches):
            for rank, (team_name, stats) in enumerate(sorted_teams, 1):
                conn.execute("""
                    INSERT INTO standings_snapshot 
                    (match_id, tournament_id, team_name, rank, played, wins, draws, losses,
                     scored, conceded, points, snapshot_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    match_id, tournament_id,
                    team_name, rank,
                    stats["played"], stats["wins"], stats["draws"], stats["losses"],
                    stats["scored"], stats["conceded"], stats["points"],
                    match_date
                ))
            snapshots_saved += 1
    
    conn.commit()
    print(f"[RESTORE] Saved {snapshots_saved} standings snapshots")
    return snapshots_saved


def _new_team_stats() -> Dict[str, int]:
    return {
        "played": 0, "wins": 0, "draws": 0, "losses": 0,
        "scored": 0, "conceded": 0, "points": 0,
    }


def _add_team_game(
    team_stats: Dict[str, Dict[str, int]],
    team: str,
    scored: int,
    conceded: int,
) -> None:
    s = team_stats[team]
    s["played"] += 1
    s["scored"] += scored
    s["conceded"] += conceded
    if scored > conceded:
        s["wins"] += 1
        s["points"] += 3
    elif scored < conceded:
        s["losses"] += 1
    else:
        s["draws"] += 1
        s["points"] += 1


def _apply_match_result(
    team_stats: Dict[str, Dict[str, int]],
    home: str,
    away: str,
    score_home: int,
    score_away: int,
    scope: str = "overall",
) -> None:
    """Применить результат матча к накопительной таблице.

    scope: 'overall' — оба участника; 'home' — только хозяин; 'away' — только гость.
    """
    if scope in ("overall", "home"):
        _add_team_game(team_stats, home, score_home, score_away)
    if scope in ("overall", "away"):
        _add_team_game(team_stats, away, score_away, score_home)


def _rank_table(
    team_stats: Dict[str, Dict[str, int]],
) -> List[Tuple[int, str, Dict[str, int]]]:
    """Ранжирование: очки DESC, разница DESC, забито DESC, имя ASC (стабильно)."""
    items = sorted(
        team_stats.items(),
        key=lambda kv: (
            -kv[1]["points"],
            -(kv[1]["scored"] - kv[1]["conceded"]),
            -kv[1]["scored"],
            kv[0],
        ),
    )
    return [(rank, name, stats) for rank, (name, stats) in enumerate(items, 1)]


def _insert_standings_snapshot(
    conn: sqlite3.Connection,
    match_id: str,
    tournament_id: str,
    table: List[Tuple[int, str, Dict[str, int]]],
    snapshot_date: str,
    table_type: str = "overall",
) -> None:
    for rank, name, stats in table:
        conn.execute(
            """
            INSERT INTO standings_snapshot
            (match_id, tournament_id, team_name, rank, played, wins, draws, losses,
             scored, conceded, points, snapshot_date, table_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id, tournament_id, name, rank,
                stats["played"], stats["wins"], stats["draws"], stats["losses"],
                stats["scored"], stats["conceded"], stats["points"],
                snapshot_date, table_type,
            ),
        )


TABLE_TYPES = ("overall", "home", "away")


def rebuild_standings_snapshots(
    conn: sqlite3.Connection, tournament_id: str
) -> Tuple[Dict[str, List[Tuple[int, str, Dict[str, int]]]], int]:
    """Восстановить 3 таблицы лиги на момент КАЖДОГО матча из истории игр.

    Для каждого матча сохраняет: overall (все матчи), home (только домашние
    матчи команд), away (только гостевые). Снимок для матча M — по итогам
    всех матчей, сыгранных строго РАНЬШЕ M.

    Возвращает (финальные таблицы по каждому типу, число снимков).
    """
    conn.execute(
        "DELETE FROM standings_snapshot WHERE tournament_id = ?", (tournament_id,)
    )

    team_names = [
        name
        for (name,) in conn.execute(
            "SELECT name FROM teams WHERE tournament_id = ? ORDER BY name",
            (tournament_id,),
        )
    ]
    stats = {tt: {name: _new_team_stats() for name in team_names} for tt in TABLE_TYPES}

    rows = conn.execute(
        """
        SELECT m.match_id, m.match_date, m.score_home, m.score_away,
               th.name AS home_team, ta.name AS away_team
        FROM matches m
        JOIN teams th ON th.id = m.home_team_id
        JOIN teams ta ON ta.id = m.away_team_id
        WHERE m.tournament_id = ?
        ORDER BY m.match_date ASC, m.match_id ASC
        """,
        (tournament_id,),
    ).fetchall()

    # row_factory не задан -> fetchall() возвращает кортежи; приводим к dict
    columns = ("match_id", "match_date", "score_home", "score_away", "home_team", "away_team")
    rows = [dict(zip(columns, row)) for row in rows]

    groups: Dict[str, List[Any]] = {}
    for row in rows:
        groups.setdefault(row["match_date"], []).append(row)

    snapshots = 0
    for match_date, group in groups.items():
        tables = {tt: _rank_table(stats[tt]) for tt in TABLE_TYPES}
        for row in group:
            for tt in TABLE_TYPES:
                _insert_standings_snapshot(
                    conn, row["match_id"], tournament_id, tables[tt], match_date, tt
                )
                snapshots += 1
        for row in group:
            sh = int(row["score_home"] or 0)
            sa = int(row["score_away"] or 0)
            _apply_match_result(stats["overall"], row["home_team"], row["away_team"], sh, sa, "overall")
            _apply_match_result(stats["home"], row["home_team"], row["away_team"], sh, sa, "home")
            _apply_match_result(stats["away"], row["home_team"], row["away_team"], sh, sa, "away")

    conn.commit()
    return {tt: _rank_table(stats[tt]) for tt in TABLE_TYPES}, snapshots


def save_team_previous_matches(
    conn: sqlite3.Connection,
    team_key: str,
    team_name: str,
    matches: List[Dict[str, Any]],
) -> int:
    """Сохранить предыдущие матчи команды (pr_ feed) в БД.

    Возвращает число сохранённых матчей.
    """
    from team_history import format_match_date

    saved = 0
    for m in matches:
        conn.execute(
            """
            INSERT OR REPLACE INTO team_previous_matches
            (team_key, team_name, match_id, kickoff_ts, match_date, competition,
             home_key, home_name, away_key, away_name, home_score, away_score, is_home)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                team_key,
                team_name or "",
                m["match_id"],
                m["kickoff_ts"],
                format_match_date(m["kickoff_ts"]),
                m["competition"],
                m["home_key"],
                m["home_name"],
                m["away_key"],
                m["away_name"],
                m["home_score"],
                m["away_score"],
                1 if m["home_key"] == team_key else 0,
            ),
        )
        saved += 1
    conn.commit()
    return saved


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Тестовая БД Flashscore API")
    sub = parser.add_subparsers(dest="command", required=True)
    
    p_test = sub.add_parser("test", help="Тест парсинга tx_ и to_ feed")
    
    p_save = sub.add_parser("save", help="Сохранить матчи и таблицу в БД")
    p_save.add_argument("--tournament-id", default="apl_2016", help="ID турнира")
    
    p_check = sub.add_parser("check", help="Проверить данные в БД")

    p_restore = sub.add_parser("restore", help="Восстановить таблицу лиги на момент каждого матча")
    p_restore.add_argument("--tournament-id", default="apl_2016", help="ID турнира")

    p_history = sub.add_parser("history", help="Спарсить последние матчи команды (pr_ feed)")
    p_history.add_argument("--team-key", required=True, help="Flashscore ключ команды (напр. nP1i5US1)")
    p_history.add_argument("--team-name", default="", help="Название команды (опционально)")
    p_history.add_argument("--country-id", type=int, default=81, help="ID страны (81=Германия)")
    p_history.add_argument("--sport", type=int, default=1, help="Вид спорта")
    p_history.add_argument("--limit", type=int, default=40, help="Сколько последних матчей")

    p_recon = sub.add_parser("reconstruct", help="Историческая реконструкция матчей команды в турнире")
    p_recon.add_argument("--team-key", required=True, help="Flashscore ключ команды")
    p_recon.add_argument("--team-name", default="", help="Название команды")
    p_recon.add_argument("--country-id", type=int, default=198, help="ID страны (198=Англия)")
    p_recon.add_argument("--sport", type=int, default=1, help="Вид спорта")
    p_recon.add_argument("--competition", default="Премьер-лига", help="Название турнира (подстрока)")
    p_recon.add_argument("--limit", type=int, default=40, help="Сколько матчей турнира")
    
    args = parser.parse_args()
    
    if args.command == "test":
        print("\nTEST: FLASHSCORE FEED PARSING")
        print("="*60)
        
        # Тест 1: tr_ feed (все страницы)
        tr_matches = test_parse_tr_feed()
        
        # Тест 2: to_ feed
        to_text, to_table = test_parse_to_feed()
        
        print("\n" + "="*60)
        print("TEST RESULT")
        print("="*60)
        print(f"tr_ feed: {len(tr_matches)} matches")
        print(f"to_ feed: {len(to_table) if to_table else 0} teams")
    
    elif args.command == "save":
        print("\nSAVE TO DB")
        print("="*60)
        
        conn = create_test_db()
        tournament_id = args.tournament_id
        
        # Добавляем турнир
        conn.execute(
            "INSERT OR IGNORE INTO tournaments (tournament_id, name, sport, season) VALUES (?, ?, ?, ?)",
            (tournament_id, "Premier League", 1, "2016")
        )
        conn.commit()
        
        # Загружаем все страницы tr_ feed
        pages = ["0", "1", "2", "3", "4"]
        all_matches = []
        
        for page in pages:
            url = f"https://46.flashscore.ninja/46/x/feed/tr_1_198_dYlOSQOD_165_{page}_1_ru-kz_1"
            text = fetch_feed(url)
            
            if not text or len(text) < 100:
                continue
            
            matches = parse_tr_feed(text)
            all_matches.extend(matches)
        
        print(f"\n[INFO] Loaded {len(all_matches)} matches from all pages")
        
        # Сохраняем команды и матчи (первые 2 уникальных)
        saved_matches = []
        seen_teams = set()
        
        for i, match in enumerate(all_matches, 1):  # Все матчи сезона (380)
            home_name = match.get("AE", "").replace("*", "")
            away_name = match.get("AF", "").replace("*", "")
            
            if not home_name or not away_name:
                continue
            
            # Добавляем команды
            for team_name in [home_name, away_name]:
                if team_name not in seen_teams:
                    conn.execute(
                        "INSERT OR IGNORE INTO teams (name, tournament_id) VALUES (?, ?)",
                        (team_name, tournament_id)
                    )
                    seen_teams.add(team_name)
            
            home_id = conn.execute(
                "SELECT id FROM teams WHERE name = ?", (home_name,)
            ).fetchone()[0]
            away_id = conn.execute(
                "SELECT id FROM teams WHERE name = ?", (away_name,)
            ).fetchone()[0]
            
            # Парсим дату (AB — служебный флаг, реальный таймстамп в AD/ADE)
            date_ts = match.get("AD", "") or match.get("ADE", "")
            if date_ts:
                try:
                    match_date = datetime.fromtimestamp(int(date_ts)).strftime("%Y.%m.%d %H:%M")
                except (ValueError, OSError):
                    match_date = "2016.08.20 17:00"
            else:
                match_date = "2016.08.20 17:00"
            
            # Сохраняем матч
            match_id = match.get("AA", f"tr_{i}")
            score_home = match.get("AT") or match.get("AG") or "0"
            score_away = match.get("AU") or match.get("AH") or "0"
            
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO matches 
                    (match_id, tournament_id, match_date, home_team_id, away_team_id,
                     score_home, score_away, match_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    match_id, tournament_id, match_date,
                    home_id, away_id,
                    int(float(score_home)), int(float(score_away)),
                    "Завершен"
                ))
            except (ValueError, TypeError):
                conn.execute("""
                    INSERT OR REPLACE INTO matches 
                    (match_id, tournament_id, match_date, home_team_id, away_team_id, match_status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    match_id, tournament_id, match_date,
                    home_id, away_id, "Не начался"
                ))
            
            saved_matches.append(match_id)
            if i <= 2:
                print(f"[OK] Match {i}: {home_name} vs {away_name} ({score_home}-{score_away})")
        
        # Загружаем to_ feed (таблица лиги)
        to_url = "https://46.flashscore.ninja/46/x/feed/to_OhnzLqf7_faBBhyuM_1"
        to_text = fetch_feed(to_url)
        to_table = parse_to_feed(to_text, table_index=1)
        
        print(f"\n[INFO] Table has {len(to_table)} teams")
        
        # Сохраняем команды из таблицы
        for i, row in enumerate(to_table, 1):
            team_name = row.get("team", "")
            if team_name:
                conn.execute(
                    "INSERT OR IGNORE INTO teams (name, tournament_id) VALUES (?, ?)",
                    (team_name, tournament_id)
                )
        conn.commit()
        
        # Сохраняем снимок таблицы для первого матча
        if saved_matches and to_table:
            match_id = saved_matches[0]
            match_row = conn.execute(
                "SELECT match_date FROM matches WHERE match_id = ?", (match_id,)
            ).fetchone()
            
            snapshot_date = match_row[0] if match_row else "2016.08.20 17:00"
            save_standings_snapshot(conn, match_id, tournament_id, to_table, snapshot_date)
            print(f"\n[OK] Standings snapshot saved for match {match_id}")
            print(f"     Snapshot date: {snapshot_date}")
            print(f"     Teams in table: {len(to_table)}")
        
        conn.close()
        print(f"\n[RESULT] Saved {len(saved_matches)} matches + standings table")
    
    elif args.command == "restore":
        print("\nRESTORE STANDINGS")
        print("=" * 60)
        conn = create_test_db()
        final_tables, snapshots = rebuild_standings_snapshots(conn, args.tournament_id)
        print(f"\n[OK] Сохранено снимков: {snapshots}")
        labels = {"overall": "ОБЩАЯ", "home": "ДОМАШНИЕ МАТЧИ", "away": "ГОСТЕВЫЕ МАТЧИ"}
        for tt in TABLE_TYPES:
            print(f"\n--- Финальная таблица: {labels[tt]} ---")
            print(f"  {'#':<3}{'Команда':<22}{'И':<4}{'В':<4}{'Н':<4}{'П':<4}"
                  f"{'ЗМ':<5}{'ПМ':<5}{'РМ':<6}{'О':<4}")
            for rank, name, s in final_tables[tt]:
                gd = s["scored"] - s["conceded"]
                print(f"  {rank:<3}{name:<22}{s['played']:<4}{s['wins']:<4}"
                      f"{s['draws']:<4}{s['losses']:<4}{s['scored']:<5}"
                      f"{s['conceded']:<5}{gd:+4d}{s['points']:<4}")
        conn.close()
    
    elif args.command == "history":
        from team_history import fetch_team_matches, format_match_date
        conn = create_test_db()
        matches = fetch_team_matches(
            args.team_key, country=args.country_id, sport=args.sport, limit=args.limit
        )
        saved = save_team_previous_matches(conn, args.team_key, args.team_name, matches)
        print(f"\n[OK] Загружено {len(matches)} матчей, сохранено {saved}")
        print("Последние матчи (от новых к старым):")
        for m in reversed(matches):
            sh = m["home_score"] if m["home_score"] is not None else "?"
            sa = m["away_score"] if m["away_score"] is not None else "?"
            print(f"  {format_match_date(m['kickoff_ts'])} | {m['home_name']} {sh}:{sa} {m['away_name']} | {m['competition']}")
        conn.close()
    
    elif args.command == "check":
        print("\nCHECK DB DATA")
        print("="*60)
        
        conn = create_test_db()
        
        # Матчи
        matches = conn.execute("""
            SELECT m.match_id, m.match_date, 
                   th.name AS home_team, ta.name AS away_team,
                   m.score_home, m.score_away
            FROM matches m
            JOIN teams th ON th.id = m.home_team_id
            JOIN teams ta ON ta.id = m.away_team_id
        """).fetchall()
        
        print(f"\nMatches ({len(matches)}):")
        for m in matches:
            print(f"  {list(m)[0]} | {list(m)[1]} | {list(m)[2]} vs {list(m)[3]} | {list(m)[4]}-{list(m)[5]}")
        
        # Таблица
        standings = conn.execute("""
            SELECT team_name, rank, played, wins, draws, losses, scored, conceded, points
            FROM standings_snapshot
            ORDER BY rank
        """).fetchall()
        
        print(f"\nTable ({len(standings)} teams):")
        print(f"  {'Rank':<6} {'Team':<25} {'P':<4} {'W':<4} {'D':<4} {'L':<4} {'GD':<8} {'Pts':<6}")
        print("  " + "-"*62)
        for s in standings:
            s_list = list(s)
            team = s_list[0]
            rank = s_list[1]
            played = s_list[2]
            wins = s_list[3]
            draws = s_list[4]
            losses = s_list[5]
            scored = s_list[6]
            conceded = s_list[7]
            points = s_list[8]
            gd = f"{scored - conceded:+d}"
            print(f"  {rank:<6} {team:<25} {played:<4} {wins:<4} {draws:<4} {losses:<4} {gd:<8} {points:<6}")
        
        conn.close()


if __name__ == "__main__":
    main()
