import sqlite3
import os
import time
import threading
import sys
from contextlib import contextmanager
from dotenv import load_dotenv
import openpyxl

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from telegram_client import TelegramNotifier
from odds_normalize import canonicalize_market, split_canonical, to_float as odds_to_float

load_dotenv()
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)


_EXCEL_ERROR_TOKENS = frozenset(
    {
        "RISK",
        "#N/A",
        "#NUM!",
        "#VALUE!",
        "#REF!",
        "#DIV/0!",
        "#NAME?",
        "#NULL!",
        "#CALC!",
        "N/A",
        "NA",
        "NONE",
    }
)


def _excel_num(*values) -> float:
    """Число из Excel-ячейки; RISK/#NUM!/мусор → пробуем следующий кандидат, иначе 0."""
    for v in values:
        if v is None or v == "":
            continue
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            # COM иногда отдаёт огромные коды ошибок; обычные вероятности/кф в разумном диапазоне
            if isinstance(v, float) and (v != v):  # NaN
                continue
            return float(v)
        if isinstance(v, str):
            s = v.strip()
            if not s or s.upper() in _EXCEL_ERROR_TOKENS or s.startswith("#"):
                continue
            parsed = odds_to_float(s)
            if parsed is not None:
                return parsed
            continue
        parsed = odds_to_float(v)
        if parsed is not None:
            return parsed
    return 0.0


def _env_bool(name, default=False):
    """Читает булево значение из переменной окружения."""
    v = os.environ.get(name, str(default)).strip().lower()
    return v in ('1', 'true', 'yes')


# Настройки из .env
DEBUG_MODE = _env_bool('DEBUG_MODE', False)
# Устарело как константа: актуальный путь — get_database_path() (читает env каждый раз).
DATABASE_PATH = os.environ.get('DATABASE_PATH', 'matches.db')
SHEET_ANALYSIS = os.environ.get('SHEET_ANALYSIS', 'Анализ')
SHEET_ARCHIVE = os.environ.get('SHEET_ARCHIVE', 'achive')
SHEET_ODDS = os.environ.get('SHEET_ODDS', 'Коэффициенты')
EXCEL_FILENAME = os.environ.get('EXCEL_FILENAME', 'DeluX_IncoProrok_mvp0.xlsm')
EXCEL_FALLBACK_PATH = os.environ.get('EXCEL_FALLBACK_PATH', r'DeluX_IncoProrok_mvp0.xlsm')


def get_database_path(explicit: str | None = None) -> str:
    """Абсолютный путь к SQLite (DATABASE_PATH из env или explicit)."""
    path = (explicit or os.environ.get("DATABASE_PATH") or "matches.db").strip()
    if not os.path.isabs(path):
        path = os.path.join(script_dir, path)
    return os.path.abspath(path)


def should_skip_onepr(db_path: str | None = None) -> bool:
    """Теневые parity_* БД и DELUX_SKIP_ONEPR=1 — без сигналов в 1pr."""
    if _env_bool("DELUX_SKIP_ONEPR", False):
        return True
    name = os.path.basename(db_path or get_database_path()).lower()
    return "parity_" in name


@contextmanager
def database_path(path: str):
    """Временно переключить DATABASE_PATH (для теневых parity_*.db)."""
    prev = os.environ.get("DATABASE_PATH")
    os.environ["DATABASE_PATH"] = path
    close_all_connections()
    try:
        yield get_database_path()
    finally:
        if prev is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = prev
        close_all_connections()


def resolve_workbook_path(explicit: str | None = None) -> str:
    """Путь к рабочей книге Excel (по умолчанию mvp0)."""
    candidates = []
    if explicit:
        candidates.append(explicit)
    candidates.extend(
        [
            os.environ.get("CALC_WORKBOOK") or "",
            EXCEL_FILENAME,
            os.path.join(script_dir, EXCEL_FILENAME),
            EXCEL_FALLBACK_PATH,
            os.path.join(script_dir, "DeluX_IncoProrok_mvp0.xlsm"),
            os.path.join(script_dir, "DeluX_IncoProrok_mvp.xlsm"),
        ]
    )
    for path in candidates:
        path = (path or "").strip()
        if not path:
            continue
        if not os.path.isabs(path):
            path = os.path.join(script_dir, path)
        if os.path.isfile(path):
            return os.path.abspath(path)
    raise FileNotFoundError(
        "Не найден Excel (.xlsm). Укажите CALC_WORKBOOK / EXCEL_FILENAME "
        "или положите DeluX_IncoProrok_mvp0.xlsm рядом со скриптом."
    )


# ============================================================================
# ОПТИМИЗАЦИИ
# ============================================================================

class ConnectionPool:
    """Пул соединений с БД для разных потоков"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._connections = {}
                    cls._instance._pool_lock = threading.Lock()
        return cls._instance
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для соединения с БД"""
        thread_id = threading.get_ident()
        path = get_database_path()
        
        with self._pool_lock:
            existing = self._connections.get(thread_id)
            if existing is not None:
                conn, conn_path = existing
                if conn_path != path:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    del self._connections[thread_id]
                    existing = None
            if thread_id not in self._connections:
                parent = os.path.dirname(path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                conn = sqlite3.connect(path, timeout=30)
                conn.row_factory = sqlite3.Row
                # Оптимизации SQLite
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=-20000")
                conn.execute("PRAGMA temp_store=MEMORY")
                conn.execute("PRAGMA mmap_size=268435456")
                self._connections[thread_id] = (conn, path)
        
        conn, _ = self._connections[thread_id]
        
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def close_all(self):
        """Закрыть все соединения"""
        with self._pool_lock:
            for item in self._connections.values():
                conn = item[0] if isinstance(item, tuple) else item
                try:
                    conn.close()
                except Exception:
                    pass
            self._connections.clear()


class QueryCache:
    """Кэш для результатов запросов"""
    def __init__(self, ttl=300):
        self._cache = {}
        self._lock = threading.Lock()
        self._ttl = ttl
    
    def get(self, key):
        with self._lock:
            if key in self._cache:
                result, timestamp = self._cache[key]
                if time.time() - timestamp < self._ttl:
                    return result
                del self._cache[key]
        return None
    
    def set(self, key, value):
        with self._lock:
            self._cache[key] = (value, time.time())
    
    def invalidate(self):
        with self._lock:
            self._cache.clear()


# Глобальные экземпляры
_pool = ConnectionPool()
_cache = QueryCache()


@contextmanager
def get_db_connection():
    """Упрощённый доступ к соединению БД"""
    with _pool.get_connection() as conn:
        yield conn


def close_all_connections():
    """Закрыть все соединения"""
    _pool.close_all()


def cached_query(query, params=(), ttl=300):
    """Выполнить запрос с кэшированием"""
    cache_key = f"{query}|{params}"
    
    # Проверяем кэш
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached
    
    # Выполняем запрос
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchall()
    
    # Сохраняем в кэш
    _cache.set(cache_key, result)
    return result


def invalidate_cache():
    """Инвалидировать кэш"""
    _cache.invalidate()


# ============================================================================
# БАЗА ДАННЫХ
# ============================================================================

def create_database(path: str | None = None):
    """Создание базы данных с индексами. path — опционально теневая БД."""
    from contextlib import nullcontext

    ctx = database_path(path) if path else nullcontext()
    with ctx:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS countries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(50) UNIQUE NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS leagues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) NOT NULL,
                    country_id INTEGER,
                    FOREIGN KEY (country_id) REFERENCES countries(id),
                    UNIQUE(name, country_id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS teams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) UNIQUE NOT NULL
                )
                """
            )
            _migrate_teams_columns(cursor)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id VARCHAR(8) UNIQUE NOT NULL,
                    match_date TEXT NOT NULL,
                    league_id INTEGER,
                    home_team_id INTEGER,
                    away_team_id INTEGER,
                    prediction VARCHAR(10),
                    match_status VARCHAR(20) DEFAULT "Не начался",
                    profit DECIMAL(10,2) DEFAULT 0.00,
                    minute VARCHAR(5) DEFAULT "90+",
                    segment VARCHAR(20) DEFAULT "0",
                    score_home INTEGER DEFAULT 0,
                    score_away INTEGER DEFAULT 0,
                    sport INTEGER DEFAULT 1 CHECK (sport BETWEEN 1 AND 99),
                    FOREIGN KEY (league_id) REFERENCES leagues(id),
                    FOREIGN KEY (home_team_id) REFERENCES teams(id),
                    FOREIGN KEY (away_team_id) REFERENCES teams(id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS odds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id VARCHAR(8) NOT NULL,
                    market_name VARCHAR(50) NOT NULL,
                    outcome VARCHAR(20),
                    side VARCHAR(20),
                    line_value DECIMAL(5,2),
                    odds_value DECIMAL(10,2),
                    FOREIGN KEY (match_id) REFERENCES matches(match_id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS goal_probabilities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id VARCHAR(8) NOT NULL,
                    home_goals_0 DECIMAL(5,2),
                    home_goals_1 DECIMAL(5,2),
                    home_goals_2 DECIMAL(5,2),
                    home_goals_3 DECIMAL(5,2),
                    home_goals_4 DECIMAL(5,2),
                    home_goals_5 DECIMAL(5,2),
                    away_goals_0 DECIMAL(5,2),
                    away_goals_1 DECIMAL(5,2),
                    away_goals_2 DECIMAL(5,2),
                    away_goals_3 DECIMAL(5,2),
                    away_goals_4 DECIMAL(5,2),
                    away_goals_5 DECIMAL(5,2),
                    FOREIGN KEY (match_id) REFERENCES matches(match_id),
                    UNIQUE(match_id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS strategies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(50) UNIQUE NOT NULL,
                    description TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id VARCHAR(8) NOT NULL,
                    strategy_id INTEGER NOT NULL,
                    prediction VARCHAR(20),
                    odds DECIMAL(10,2),
                    stake DECIMAL(10,2),
                    result VARCHAR(20),
                    profit DECIMAL(10,2),
                    notes TEXT,
                    FOREIGN KEY (match_id) REFERENCES matches(match_id),
                    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sub_strategies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name VARCHAR(50) UNIQUE NOT NULL,
                    description TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS outcome_probabilities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id VARCHAR(8) NOT NULL,
                    strategy_id INTEGER NOT NULL,
                    home_win_prob DECIMAL(5,2),
                    draw_prob DECIMAL(5,2),
                    away_win_prob DECIMAL(5,2),
                    FOREIGN KEY (match_id) REFERENCES matches(match_id),
                    FOREIGN KEY (strategy_id) REFERENCES sub_strategies(id),
                    UNIQUE(match_id, strategy_id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS match_missing_players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id VARCHAR(8) NOT NULL,
                    side VARCHAR(8) NOT NULL,
                    player_id VARCHAR(32) NOT NULL DEFAULT '',
                    player_name TEXT,
                    list_name TEXT,
                    team_name TEXT,
                    participant_url TEXT,
                    team_logos TEXT,
                    event_participant_id TEXT,
                    source_bucket TEXT,
                    reason TEXT,
                    category TEXT,
                    is_unsure INTEGER NOT NULL DEFAULT 0,
                    raw_json TEXT,
                    fetched_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(match_id, side, player_id, reason, is_unsure)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS moneyway (
                    match_id VARCHAR(8) PRIMARY KEY,
                    home_name TEXT,
                    away_name TEXT,
                    found INTEGER NOT NULL DEFAULT 0,
                    market_id TEXT,
                    coef_1 REAL,
                    coef_x REAL,
                    coef_2 REAL,
                    volume_1 REAL,
                    volume_x REAL,
                    volume_2 REAL,
                    volume_floor REAL,
                    league TEXT,
                    event_start TEXT,
                    has_signal INTEGER NOT NULL DEFAULT 0,
                    signal_side VARCHAR(8),
                    signal_odds REAL,
                    raw_json TEXT,
                    fetched_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (match_id) REFERENCES matches(match_id)
                )
                """
            )
            _migrate_missing_players_columns(cursor)
            for idx in (
                "CREATE INDEX IF NOT EXISTS idx_odds_match_id ON odds(match_id)",
                "CREATE INDEX IF NOT EXISTS idx_matches_match_id ON matches(match_id)",
                "CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date)",
                "CREATE INDEX IF NOT EXISTS idx_strategy_predictions_match ON strategy_predictions(match_id)",
                "CREATE INDEX IF NOT EXISTS idx_outcome_probabilities_match ON outcome_probabilities(match_id)",
                "CREATE INDEX IF NOT EXISTS idx_goal_probabilities_match ON goal_probabilities(match_id)",
                "CREATE INDEX IF NOT EXISTS idx_missing_players_match ON match_missing_players(match_id)",
                "CREATE INDEX IF NOT EXISTS idx_missing_players_player ON match_missing_players(player_id)",
                "CREATE INDEX IF NOT EXISTS idx_moneyway_signal ON moneyway(has_signal)",
                "CREATE INDEX IF NOT EXISTS idx_moneyway_fetched ON moneyway(fetched_at)",
            ):
                cursor.execute(idx)
            _ensure_main_strategies(cursor)
            conn.commit()


def _migrate_missing_players_columns(cursor) -> None:
    """Добавляет новые колонки в match_missing_players на существующих БД."""
    rows = cursor.execute("PRAGMA table_info(match_missing_players)").fetchall()
    existing = {row[1] for row in rows}
    for name, col_type in (
        ("list_name", "TEXT"),
        ("participant_url", "TEXT"),
        ("team_logos", "TEXT"),
        ("event_participant_id", "TEXT"),
        ("source_bucket", "TEXT"),
        ("raw_json", "TEXT"),
    ):
        if name not in existing:
            cursor.execute(f"ALTER TABLE match_missing_players ADD COLUMN {name} {col_type}")


def _migrate_teams_columns(cursor) -> None:
    """Flashscore name остаётся в name; внешние сервисы — отдельные колонки."""
    rows = cursor.execute("PRAGMA table_info(teams)").fetchall()
    existing = {row[1] for row in rows}
    if "name_arbworld" not in existing:
        cursor.execute("ALTER TABLE teams ADD COLUMN name_arbworld TEXT")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_teams_name_arbworld ON teams(name_arbworld)"
    )


def _ensure_main_strategies(cursor) -> None:
    """Основные стратегии DeluX (NTB / Betalone / Sniper / BTS)."""
    defaults = (
        (1, "NTB", "DeluX NTB (лист Анализ S13)"),
        (2, "Betalone", "DeluX Betalone (O10)"),
        (3, "Sniper", "DeluX Sniper (X24)"),
        (4, "BTS", "Обе забьют — очные 2/2 в последних 5 играх"),
        (5, "Favorites", "Победа фаворита — оптимальный диапазон кф (backtest)"),
        (6, "StavkaTV", "Прогнозы tipster'ов stavka.tv (4 прогнозиста)"),
        (7, "Moneyway", "Arbworld moneyway: max odds = max volume, vol > 1000"),
        (8, "1pr", "Исход с макс. вероятностью подстратегии «1 пр»"),
    )
    for sid, name, desc in defaults:
        row = cursor.execute("SELECT id FROM strategies WHERE name = ?", (name,)).fetchone()
        if row and int(row[0]) != sid:
            cursor.execute(
                "UPDATE strategies SET name = ? WHERE id = ?",
                (f"{name}_legacy_{row[0]}", row[0]),
            )
            cursor.execute(
                "UPDATE strategy_predictions SET strategy_id = ? WHERE strategy_id = ?",
                (sid, row[0]),
            )
        cursor.execute(
            """
            INSERT INTO strategies (id, name, description)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description
            """,
            (sid, name, desc),
        )


BTS_STRATEGY_ID = 4
FAVORITES_STRATEGY_ID = 5
STAVKA_TV_STRATEGY_ID = 6
DOGS_STRATEGY_ID = 7
ONEPR_STRATEGY_ID = 8


def upsert_strategy_prediction(
    match_id: str,
    strategy_id: int,
    prediction: str,
    *,
    odds: float | None = None,
    notes: str | None = None,
) -> None:
    """Один прогноз по стратегии на матч (update или insert)."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id FROM strategy_predictions WHERE match_id = ? AND strategy_id = ?",
            (match_id, strategy_id),
        ).fetchone()
        if row:
            conn.execute(
                """
                UPDATE strategy_predictions
                SET prediction = ?, odds = COALESCE(?, odds), notes = COALESCE(?, notes)
                WHERE id = ?
                """,
                (prediction, odds, notes, row["id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO strategy_predictions (match_id, strategy_id, prediction, odds, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (match_id, strategy_id, prediction, odds, notes),
            )
        conn.commit()


def upsert_moneyway(match_id: str, snap: dict) -> None:
    """Снимок Arbworld Moneyway по матчу (на каждый анализ)."""
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO moneyway (
                match_id, home_name, away_name, found, market_id,
                coef_1, coef_x, coef_2, volume_1, volume_x, volume_2,
                volume_floor, league, event_start, has_signal, signal_side,
                signal_odds, raw_json, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(match_id) DO UPDATE SET
                home_name = excluded.home_name,
                away_name = excluded.away_name,
                found = excluded.found,
                market_id = excluded.market_id,
                coef_1 = excluded.coef_1,
                coef_x = excluded.coef_x,
                coef_2 = excluded.coef_2,
                volume_1 = excluded.volume_1,
                volume_x = excluded.volume_x,
                volume_2 = excluded.volume_2,
                volume_floor = excluded.volume_floor,
                league = excluded.league,
                event_start = excluded.event_start,
                has_signal = excluded.has_signal,
                signal_side = excluded.signal_side,
                signal_odds = excluded.signal_odds,
                raw_json = excluded.raw_json,
                fetched_at = excluded.fetched_at
            """,
            (
                match_id,
                snap.get("home_name") or snap.get("home"),
                snap.get("away_name") or snap.get("away"),
                1 if snap.get("found") else 0,
                snap.get("market_id"),
                snap.get("coef_1"),
                snap.get("coef_x"),
                snap.get("coef_2"),
                snap.get("volume_1"),
                snap.get("volume_x"),
                snap.get("volume_2"),
                snap.get("volume_floor"),
                snap.get("league"),
                snap.get("event_start"),
                1 if snap.get("has_signal") else 0,
                snap.get("signal_side"),
                snap.get("signal_odds"),
                snap.get("raw_json"),
            ),
        )
        conn.commit()


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def parse_league(league_str):
    """Разделение строки лиги на страну и название лиги"""
    if ': ' in league_str:
        country, league = league_str.split(': ', 1)
        return country.strip(), league.strip()
    return 'Unknown', league_str


def insert_or_get_country(cursor, country_name):
    """Добавление страны или получение её ID (с кэшем)"""
    result = cached_query('SELECT id FROM countries WHERE name = ?', (country_name,), ttl=3600)
    if result:
        return result[0]['id']
    
    cursor.execute('INSERT INTO countries (name) VALUES (?)', (country_name,))
    invalidate_cache()
    return cursor.lastrowid


def insert_or_get_league(cursor, league_name, country_id):
    """Добавление лиги или получение её ID (с кэшем)"""
    result = cached_query(
        'SELECT id FROM leagues WHERE name = ? AND country_id = ?', 
        (league_name, country_id), ttl=3600
    )
    if result:
        return result[0]['id']
    
    cursor.execute('INSERT INTO leagues (name, country_id) VALUES (?, ?)', (league_name, country_id))
    invalidate_cache()
    return cursor.lastrowid


def insert_or_get_team(cursor, team_name):
    """Добавление команды или получение её ID (с кэшем). name = Flashscore."""
    result = cached_query('SELECT id FROM teams WHERE name = ?', (team_name,), ttl=3600)
    if result:
        return result[0]['id']
    
    cursor.execute('INSERT INTO teams (name) VALUES (?)', (team_name,))
    invalidate_cache()
    return cursor.lastrowid


def load_team_name_map(service: str = "arbworld") -> dict[str, str]:
    """
    Flashscore name (casefold) → имя во внешнем сервисе.
    Если алиаса нет — ключ не включается (caller использует исходное имя).
    """
    col = {
        "arbworld": "name_arbworld",
    }.get(service)
    if not col:
        return {}
    out: dict[str, str] = {}
    with get_db_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT name, {col} AS alias
            FROM teams
            WHERE {col} IS NOT NULL AND TRIM({col}) != ''
            """
        ).fetchall()
    for row in rows:
        fs = (row["name"] if hasattr(row, "keys") else row[0]) or ""
        alias = (row["alias"] if hasattr(row, "keys") else row[1]) or ""
        fs_key = str(fs).strip().casefold()
        alias_s = str(alias).strip()
        if fs_key and alias_s:
            out[fs_key] = alias_s
    return out


def resolve_service_team_name(flashscore_name: str, service: str = "arbworld") -> str:
    """Вернуть имя для сервиса или исходное Flashscore-имя."""
    mapping = load_team_name_map(service)
    key = (flashscore_name or "").strip().casefold()
    return mapping.get(key) or (flashscore_name or "").strip()


# ============================================================================
# РАБОТА С EXCEL
# ============================================================================

def read_excel_file(file_path):
    """Оптимизированное чтение Excel файла (read_only режим)"""
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
        
        if SHEET_ARCHIVE not in wb.sheetnames:
            print(f"Лист '{SHEET_ARCHIVE}' не найден")
            wb.close()
            return None
        
        sheet = wb[SHEET_ARCHIVE]
        max_row = sheet.max_row
        
        if max_row < 2:
            wb.close()
            return None
        
        data_row = max_row
        
        # Чтение только нужных колонок
        columns_map = {
            'A': 'id', 'B': 'sport', 'C': 'match_date', 'D': 'league',
            'E': 'home', 'F': 'away',
            'K': 'prediction',  # прогноз NTB из архива
            'AJ': 'strategy_pred_1',
            'AK': 'strategy_pred_2', 'BK': 'strategy_pred_3'
        }
        
        data = {}
        for col_letter, key in columns_map.items():
            cell_value = sheet[f"{col_letter}{data_row}"].value
            data[key] = str(cell_value) if cell_value is not None else ''
        
        wb.close()
        
        # Если в архиве нет прогноза — взять с листа Анализ (S13)
        if not str(data.get('prediction') or '').strip():
            try:
                wb2 = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
                if SHEET_ANALYSIS in wb2.sheetnames:
                    pred = wb2[SHEET_ANALYSIS]['S13'].value
                    if pred is not None and not (isinstance(pred, int) and pred < 0):
                        data['prediction'] = str(pred).strip()
                wb2.close()
            except Exception:
                pass
        
        # Чтение коэффициентов
        odds_data = _read_odds_sheet_optimized(file_path)
        data['odds_data'] = odds_data
        
        return data
        
    except Exception as e:
        print(f"Ошибка при чтении Excel: {e}")
        return None


def _read_odds_sheet_optimized(file_path):
    """Чтение листа коэффициентов (вертикальная раскладка по БК)."""
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)

        if SHEET_ODDS not in wb.sheetnames:
            wb.close()
            return None

        sheet = wb[SHEET_ODDS]
        last_col = sheet.max_column or 1
        last_row = sheet.max_row or 1

        home_id = sheet.cell(row=2, column=1).value
        away_id = sheet.cell(row=2, column=2).value

        # market_name -> max current odds across all bookmakers
        max_odds = {}

        col = 3
        while col <= last_col:
            title = sheet.cell(row=1, column=col).value
            if title is None and sheet.cell(row=2, column=col).value is None:
                break

            for row in range(3, last_row + 1):
                market_name = sheet.cell(row=row, column=col).value
                if market_name is None or str(market_name).strip() == '':
                    break
                current = sheet.cell(row=row, column=col + 2).value
                if current is None:
                    continue
                odds_val = odds_to_float(current)
                if odds_val is None or odds_val <= 1:
                    continue
                key = str(market_name).strip().upper()
                if key not in max_odds or odds_val > max_odds[key]["odds_value"]:
                    market_info = _parse_market_header(key, odds_val)
                    if market_info:
                        max_odds[key] = market_info

            col += 3

        wb.close()
        return {
            'home_id': home_id,
            'away_id': away_id,
            'markets': list(max_odds.values()),
        }

    except Exception as e:
        print(f"Ошибка при чтении odds: {e}")
        return None


def _parse_market_header(header, odds_val):
    """Парсинг заголовка рынка → каноническое имя (1X2_1, OVER 2.5, …)."""
    canon = canonicalize_market(str(header or "").strip())
    if not canon:
        return None
    meta = split_canonical(canon)
    return {
        "market_name": canon,
        "outcome": meta.get("outcome"),
        "side": meta.get("side"),
        "line_value": meta.get("line_value"),
        "odds_value": odds_val,
    }


# ============================================================================
# ВСТАВКА ДАННЫХ В БД
# ============================================================================

def insert_match_data(item, excel_file_path=None):
    """Вставка данных матча"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        match_id = str(item.get('id', '')) if 'id' in item else str(item.get('match_id', ''))
        from date_utils import normalize_match_date
        match_date = normalize_match_date(item.get('match_date', ''))
        league_str = item.get('league', '')
        home_team = item.get('home', '')
        away_team = item.get('away', '')
        prediction = item.get('prediction', '')
        try:
            sport = int(float(item.get('sport') or 1))
        except (TypeError, ValueError):
            sport = 1
        
        country_name, league_name = parse_league(league_str)
        country_id = insert_or_get_country(cursor, country_name)
        league_id = insert_or_get_league(cursor, league_name, country_id)
        home_team_id = insert_or_get_team(cursor, home_team)
        away_team_id = insert_or_get_team(cursor, away_team)
        
        cursor.execute('''
        INSERT OR REPLACE INTO matches 
        (match_id, match_date, league_id, home_team_id, away_team_id, prediction, sport)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (match_id, match_date, league_id, home_team_id, away_team_id, prediction, sport))
        
        # Вставка стратегий
        strategy_predictions = {
            1: item.get('strategy_pred_1', ''),
            2: item.get('strategy_pred_2', ''),
            3: item.get('strategy_pred_3', '')
        }
        _insert_strategy_predictions(conn, match_id, strategy_predictions)
        
        # Вставка коэффициентов
        odds_data = item.get('odds_data')
        if not odds_data and excel_file_path:
            odds_data = _read_odds_sheet_optimized(excel_file_path)
        
        if odds_data and odds_data.get('markets'):
            cursor.execute('DELETE FROM odds WHERE match_id = ?', (match_id,))
            
            odds_batch = [
                (match_id, m['market_name'], m['outcome'], m['side'], m['line_value'], m['odds_value'])
                for m in odds_data['markets']
            ]
            
            cursor.executemany('''
            INSERT INTO odds (match_id, market_name, outcome, side, line_value, odds_value)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', odds_batch)
            
            print(f"[odds] Inserted {len(odds_batch)} odds markets for {match_id}")
        
        conn.commit()
        return True


def _insert_strategy_predictions(conn, match_id, strategy_predictions):
    """Вставка прогнозов по стратегиям"""
    cursor = conn.cursor()
    
    for strategy_id, prediction in strategy_predictions.items():
        if prediction and prediction.strip():
            cursor.execute('''
            INSERT OR REPLACE INTO strategy_predictions 
            (match_id, strategy_id, prediction)
            VALUES (?, ?, ?)
            ''', (match_id, strategy_id, prediction.strip()))


def insert_goal_probabilities(excel_file_path, match_id):
    """Чтение и вставка вероятностей голов"""
    try:
        wb = openpyxl.load_workbook(excel_file_path, data_only=True)
        
        if SHEET_ANALYSIS not in wb.sheetnames:
            print(f"[-] List '{SHEET_ANALYSIS}' ne nayden")
            wb.close()
            return False
        
        sheet = wb[SHEET_ANALYSIS]
        home_goals, away_goals = _extract_goal_probabilities(sheet)
        
        if DEBUG_MODE:
            _print_goal_probabilities_debug(match_id, home_goals, away_goals)
            wb.close()
            return True
        
        # Сохранение в БД
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            home_percent = [p * 100 for p in home_goals]
            away_percent = [p * 100 for p in away_goals]
            
            cursor.execute('''
            INSERT OR REPLACE INTO goal_probabilities 
            (match_id, home_goals_0, home_goals_1, home_goals_2, home_goals_3, home_goals_4, home_goals_5,
             away_goals_0, away_goals_1, away_goals_2, away_goals_3, away_goals_4, away_goals_5)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (match_id, *home_percent, *away_percent))
            
            conn.commit()
        
        print(f"\n[+] Veroyatnosti golov sohraneny dlya matcha {match_id}")
        wb.close()
        return True
        
    except Exception as e:
        print(f"[-] Oshibka: {e}")
        return False


def _extract_goal_probabilities(sheet):
    """Извлечение вероятностей голов из листа"""
    home_columns = [22, 23, 24, 25, 26, 27]
    away_columns = [35, 36, 37, 38, 39, 40]
    data_rows = [10, 11]
    
    home_goals = []
    away_goals = []
    
    for col in home_columns:
        home_goals.append(
            _excel_num(
                sheet.cell(row=data_rows[0], column=col).value,
                sheet.cell(row=data_rows[1], column=col).value,
            )
        )
    
    for col in away_columns:
        away_goals.append(
            _excel_num(
                sheet.cell(row=data_rows[0], column=col).value,
                sheet.cell(row=data_rows[1], column=col).value,
            )
        )
    
    return home_goals, away_goals


def _print_goal_probabilities_debug(match_id, home_goals, away_goals):
    """Вывод вероятностей голов в режиме отладки"""
    print("\n" + "=" * 70)
    print("[debug] REZHIM OTLADKI: Veroyatnosti golov NE sohranyayutsya v BD")
    print("=" * 70)
    print(f"[debug] Dannye dlya matcha {match_id}:")
    
    goals_labels = ['0', '1', '2', '3', '4', '5+']
    print("\n[debug] Hozyaeva:")
    for i, prob in enumerate(home_goals):
        print(f"  • {goals_labels[i]:2} golov: {prob:.4f} ({prob*100:.2f}%)")
    
    print("\n[debug] Gosti:")
    for i, prob in enumerate(away_goals):
        print(f"  • {goals_labels[i]:2} golov: {prob:.4f} ({prob*100:.2f}%)")
    
    print("\n" + "=" * 70)


def insert_outcome_probabilities_from_analysis(excel_file_path, match_id):
    """Чтение и вставка вероятностей исходов для подстратегий"""
    try:
        wb = openpyxl.load_workbook(excel_file_path, data_only=True)
        
        if SHEET_ANALYSIS not in wb.sheetnames:
            print(f"[-] List '{SHEET_ANALYSIS}' ne nayden")
            wb.close()
            return False
        
        sheet = wb[SHEET_ANALYSIS]
        probabilities = _extract_outcome_probabilities(sheet)
        
        if DEBUG_MODE:
            _print_outcome_probabilities_debug(match_id, probabilities)
            wb.close()
            return True
        
        # Получение стратегий из БД
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, strategy_name FROM sub_strategies ORDER BY id')
            strategies = cursor.fetchall()
            
            if len(strategies) < 10:
                _insert_default_sub_strategies(cursor)
                cursor.execute('SELECT id, strategy_name FROM sub_strategies ORDER BY id')
                strategies = cursor.fetchall()
            
            # Сохранение вероятностей
            for i, prob_data in enumerate(probabilities):
                if i < len(strategies):
                    cursor.execute('''
                    INSERT OR REPLACE INTO outcome_probabilities 
                    (match_id, strategy_id, home_win_prob, draw_prob, away_win_prob)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (
                        match_id, strategies[i][0],
                        prob_data['home_prob'] * 100,
                        prob_data['draw_prob'] * 100,
                        prob_data['away_prob'] * 100
                    ))
            
            conn.commit()
        
        print(f"\n[+] Veroyatnosti ishodov sohraneny dlya matcha {match_id}")
        wb.close()
        try:
            from db import should_skip_onepr
            from onepr_hook import sync_1pr_signal

            if not should_skip_onepr():
                sync_1pr_signal(match_id)
        except Exception as exc:
            print(f"[1pr] hook failed: {exc}")
        return True
        
    except Exception as e:
        print(f"[-] Oshibka: {e}")
        return False


def _extract_outcome_probabilities(sheet):
    """Извлечение вероятностей исходов для 10 подстратегий"""
    probabilities = []
    start_row = 8
    
    for strategy_idx in range(10):
        current_row = start_row + (strategy_idx * 2)
        
        if current_row + 1 > 28:
            break
        
        # H/I — П1, J/(J+1) — X, K/L — П2.
        # Важно: ячейка может содержать текст RISK (не None) — тогда берём запасную.
        home_prob = _excel_num(
            sheet.cell(row=current_row, column=8).value,
            sheet.cell(row=current_row, column=9).value,
        )
        draw_prob = _excel_num(
            sheet.cell(row=current_row, column=10).value,
            sheet.cell(row=current_row + 1, column=10).value,
        )
        away_prob = _excel_num(
            sheet.cell(row=current_row, column=11).value,
            sheet.cell(row=current_row, column=12).value,
        )
        
        probabilities.append({
            'strategy_idx': strategy_idx,
            'home_prob': home_prob,
            'draw_prob': draw_prob,
            'away_prob': away_prob,
            'row': current_row
        })
    
    return probabilities


def _print_outcome_probabilities_debug(match_id, probabilities):
    """Вывод вероятностей исходов в режиме отладки"""
    print("\n" + "=" * 70)
    print("[debug] REZHIM OTLADKI: Veroyatnosti NE sohranyayutsya v BD")
    print("=" * 70)
    print(f"[debug] Dannye dlya matcha {match_id}:")
    
    for prob in probabilities:
        total = prob['home_prob'] + prob['draw_prob'] + prob['away_prob']
        print(f"\n  [debug] Strategiya {prob['strategy_idx'] + 1} (stroki {prob['row']}-{prob['row'] + 1}):")
        print(f"      Pobeda hozyaev: {prob['home_prob']:.4f} ({prob['home_prob'] * 100:.2f}%)")
        print(f"      Nich'ya:         {prob['draw_prob']:.4f} ({prob['draw_prob'] * 100:.2f}%)")
        print(f"      Pobeda gostey: {prob['away_prob']:.4f} ({prob['away_prob'] * 100:.2f}%)")
        print(f"      {'[OK]' if abs(total - 1.0) < 0.01 else '[WARN]'} Summa: {total:.4f} ({total * 100:.2f}%)")
    
    print("\n" + "=" * 70)


def _insert_default_sub_strategies(cursor):
    """Вставка подстратегий по умолчанию"""
    default_strategies = [
        ('sub_strat_1', 'Подстратегия 1'),
        ('sub_strat_2', 'Подстратегия 2'),
        ('sub_strat_3', 'Подстратегия 3'),
        ('sub_strat_4', 'Подстратегия 4'),
        ('sub_strat_5', 'Подстратегия 5'),
        ('sub_strat_6', 'Подстратегия 6'),
        ('sub_strat_7', 'Подстратегия 7'),
        ('sub_strat_8', 'Подстратегия 8'),
        ('sub_strat_9', 'Подстратегия 9'),
        ('sub_strat_10', 'Подстратегия 10'),
    ]
    
    for name, desc in default_strategies:
        cursor.execute('''
        INSERT OR IGNORE INTO sub_strategies (strategy_name, description)
        VALUES (?, ?)
        ''', (name, desc))


# ============================================================================
# ОСНОВНОЙ БЛОК
# ============================================================================

def insert_outcome_probabilities_from_values(match_id: str, probabilities: list) -> bool:
    """Сохраняет вероятности исходов из Python-структуры."""
    if not probabilities:
        return False
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sub_strategies")
            if cursor.fetchone()[0] < 10:
                _insert_default_sub_strategies(cursor)
            cursor.execute("SELECT id FROM sub_strategies ORDER BY id")
            strategies = [row[0] for row in cursor.fetchall()]
            for i, prob in enumerate(probabilities):
                if i >= len(strategies):
                    break
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO outcome_probabilities
                    (match_id, strategy_id, home_win_prob, draw_prob, away_win_prob)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        match_id,
                        strategies[i],
                        float(prob.get("home_prob", 0)) * 100,
                        float(prob.get("draw_prob", 0)) * 100,
                        float(prob.get("away_prob", 0)) * 100,
                    ),
                )
        return True
    except Exception as e:
        print(f"[-] outcome probabilities: {e}")
        return False


def insert_goal_probabilities_from_values(match_id: str, home_goals: list, away_goals: list) -> bool:
    """Сохраняет вероятности голов из Python-списков."""
    if not home_goals and not away_goals:
        return False
    try:
        home = (list(home_goals) + [0] * 6)[:6]
        away = (list(away_goals) + [0] * 6)[:6]
        home_pct = [float(v) * 100 for v in home]
        away_pct = [float(v) * 100 for v in away]
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO goal_probabilities
                (match_id, home_goals_0, home_goals_1, home_goals_2, home_goals_3, home_goals_4, home_goals_5,
                 away_goals_0, away_goals_1, away_goals_2, away_goals_3, away_goals_4, away_goals_5)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (match_id, *home_pct, *away_pct),
            )
        return True
    except Exception as e:
        print(f"[-] goal probabilities: {e}")
        return False


def insert_match_data_with_probabilities(item, excel_file_path):
    """Вставка данных матча вместе с вероятностями"""
    success = insert_match_data(item, excel_file_path)
    
    if success:
        match_id = str(item.get('id', '')) if 'id' in item else str(item.get('match_id', ''))
        insert_outcome_probabilities_from_analysis(excel_file_path, match_id)
        insert_goal_probabilities(excel_file_path, match_id)
    
    return success


def clear_table(table_name):
    """Очистка таблицы"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f'DELETE FROM {table_name}')
        cursor.execute('DELETE FROM sqlite_sequence WHERE name = ?', (table_name,))
        conn.commit()
        print(f"[+] Tablica '{table_name}' ochischena")


def get_strategy_probabilities(match_id, strategy_name):
    """Получение вероятностей для стратегии"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT o.home_win_prob, o.draw_prob, o.away_win_prob
        FROM outcome_probabilities o
        JOIN sub_strategies s ON o.strategy_id = s.id
        WHERE o.match_id = ? AND s.strategy_name = ?
        ''', (match_id, strategy_name))
        result = cursor.fetchone()
    
    if result:
        return {'home': result[0], 'draw': result[1], 'away': result[2]}
    return None


def get_goal_probabilities(match_id):
    """Получение вероятностей голов"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT home_goals_0, home_goals_1, home_goals_2, home_goals_3, home_goals_4, home_goals_5,
               away_goals_0, away_goals_1, away_goals_2, away_goals_3, away_goals_4, away_goals_5
        FROM goal_probabilities
        WHERE match_id = ?
        ''', (match_id,))
        result = cursor.fetchone()
    
    if result:
        return {'home': result[:6], 'away': result[6:]}
    return None


def verify_strategies_in_db():
    """Проверка наличия подстратегий в БД"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM sub_strategies')
        count = cursor.fetchone()[0]
        
        if count < 10:
            _insert_default_sub_strategies(cursor)
            conn.commit()
        
        cursor.execute('SELECT id, strategy_name FROM sub_strategies ORDER BY id')
        strategies = cursor.fetchall()
    
    print("\n[*] Strategii v baze:")
    for strat in strategies:
        print(f"  ID {strat[0]}: {strat[1]}")
    
    return strategies


# ============================================================================
if __name__ == "__main__":
    try:
        print(f"\n{'=' * 60}")
        mode = "OTLADKA (tol'ko vyvod)" if DEBUG_MODE else "RABOCHIY (sohranenie v BD)"
        print(f"REZHIM RABOTY: {mode}")
        print(f"{'=' * 60}\n")
        
        # Создание БД
        create_database()
        
        # Определение пути к Excel (mvp0 по умолчанию)
        excel_file_path = resolve_workbook_path()
        print(f"[*] Excel: {excel_file_path}")
        
        # Чтение данных
        data = read_excel_file(excel_file_path)
        
        if data is not None:
            success = insert_match_data_with_probabilities(data, excel_file_path)
            
            # Отправка в Telegram
            telegram = TelegramNotifier()
            if success and telegram.is_configured and not DEBUG_MODE:
                message_text = f"""
[+] Prognoz na match:
Data: {data.get('match_date', 'N/D')}
Turnir: {data.get('league', 'N/D')}
Komandy: {data.get('home', 'N/D')} - {data.get('away', 'N/D')}
Prognoz: {data.get('prediction', 'N/D')}
"""
                if telegram.send(message_text):
                    print("[+] Dannye otpravleny v Telegram!")
        else:
            print("[-] Ne udalos' prochitat' dannye iz Excel")
    
    except Exception as e:
        print(f"[-] Oshibka: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        close_all_connections()
        print("\n[+] Rabota zavershena")