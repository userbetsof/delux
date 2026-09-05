"""Настройки DeluX из .env (замена листа «Старт»)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

from analysis_data import MatchSettings, build_settings

load_dotenv()

SCRIPT_DIR = Path(__file__).resolve().parent


def _resolve_workbook_path(workbook_path: str) -> str:
    """Проверка пути к книге без импорта win32com (нужно в Docker)."""
    path = Path(workbook_path).expanduser()
    if not path.is_absolute():
        path = (SCRIPT_DIR / path).resolve()
    else:
        path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Workbook not found: {path}")
    return str(path)

# ID видов спорта (Старт!R2 / Flashscore): 1 футбол, 3 баскетбол, 4 хоккей, 6 бейсбол.
ALL_SPORTS = (1, 3, 4, 6)

DEFAULT_LEAGUES = (
    "Англия: Премьер-лига",
    "Испания: Примера",
    "Италия: Серия А",
    "Франция: Первая лига",
    "Германия: Бундеслига",
    "Португалия: Чемпионат Португалии",
    "РОССИЯ: Премьер-лига",
)

DEFAULT_BASKETBALL_LEAGUES = (
    "США: NBA",
    "ЕВРОПА: Евролига",
    "ИСПАНИЯ: ACB",
)

DEFAULT_HOCKEY_LEAGUES = (
    "Беларусь: Экстралига",
    "Дания: Метал-лига",
    "Польша: Польская Хоккейная Лига",
    "Россия: ФОНБЕТ КХЛ",
    "США: НХЛ",
    "Финляндия: Высшая лига",
    "Чехия: Экстралига",
    "Швеция: Элитсериен",
)

BASEBALL_LEAGUES = (
    "США: МЛБ",
    "ЯПОНИЯ: Павапуро",
    "ЮЖНАЯ КОРЕЯ: КБО",
)

DEFAULT_LEAGUES_BY_SPORT: dict[int, tuple[str, ...]] = {
    1: DEFAULT_LEAGUES,
    3: DEFAULT_BASKETBALL_LEAGUES,
    4: DEFAULT_HOCKEY_LEAGUES,
    6: BASEBALL_LEAGUES,
}


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name, str(default)).strip().lower()
    return v in ("1", "true", "yes")


def _parse_leagues(raw: str) -> Optional[List[str]]:
    token = raw.strip()
    if token in ("*", "ALL", "all"):
        return None
    if not token:
        return list(DEFAULT_LEAGUES)
    return [part.strip() for part in token.split(",") if part.strip()]


def normalize_sport_id(sport_id: int) -> int:
    """ID вида для ленты Flashscore (= DeluX id)."""
    return int(sport_id)


def queue_sport_id(sport_id: int) -> int:
    """ID вида для очереди/БД."""
    return int(sport_id)


def calc_sport_id(sport_id: int) -> int:
    """ID для Старт!R2 и формул Excel."""
    return int(sport_id)


def sport_id_aliases(sport_id: int) -> tuple[int, ...]:
    return (int(sport_id),)


@dataclass
class DeluxSettings:
    sport: int = 1
    source: int = 2
    tz_base: int = 16
    dayzone_base: int = 8
    time_offset: int = 10
    leagues: Optional[List[str]] = field(default_factory=lambda: list(DEFAULT_LEAGUES))
    leagues_by_sport: Dict[int, Optional[List[str]]] = field(default_factory=dict)
    sports_auto: List[int] = field(default_factory=lambda: list(ALL_SPORTS))
    use_excel_io: bool = False
    calc_backend: str = "python"
    formula_pure_eval: bool = True
    calc_workbook: str = ""
    database_path: str = "matches.db"
    min_tour_games: int = 5

    @property
    def match_settings(self) -> MatchSettings:
        return build_settings(
            sport=self.sport,
            source=self.source,
            tz_base=self.tz_base,
            dayzone_base=self.dayzone_base,
            time_offset=self.time_offset,
        )

    @property
    def timezone(self) -> int:
        return self.tz_base - (13 + self.time_offset)

    @property
    def dayzone(self) -> int:
        return self.dayzone_base - 8

    def resolve_calc_workbook(self) -> str:
        if self.calc_workbook:
            path = Path(self.calc_workbook)
            if not path.is_absolute():
                path = SCRIPT_DIR / path
            if path.is_file():
                return _resolve_workbook_path(str(path))
        for candidate in (
            os.environ.get("CALC_WORKBOOK", ""),
            os.environ.get("EXCEL_FILENAME", "DeluX_IncoProrok_mvp.xlsm"),
            os.environ.get("EXCEL_FALLBACK_PATH", ""),
            "DeluX_IncoProrok_mvp.xlsm",
            "DeluX_IncoProrok_mvp0.xlsm",
        ):
            if not candidate:
                continue
            path = Path(candidate)
            if not path.is_absolute():
                path = SCRIPT_DIR / path
            if path.is_file():
                return _resolve_workbook_path(str(path))
        raise FileNotFoundError(
            "Не найден .xlsm для расчёта формул. Укажите CALC_WORKBOOK в .env"
        )

    def list_auto_default(self) -> bool:
        """Загружать все виды из DELUX_SPORTS_AUTO без явного --auto."""
        raw = os.environ.get("DELUX_AUTO", "").strip()
        if raw:
            return _env_bool("DELUX_AUTO", False)
        return len(self.sports_auto) > 1

    def leagues_for_sport(self, sport_id: int) -> Optional[List[str]]:
        sport_id = int(sport_id)
        if sport_id == 1:
            return self.leagues
        if sport_id in self.leagues_by_sport:
            return self.leagues_by_sport[sport_id]
        defaults = DEFAULT_LEAGUES_BY_SPORT.get(sport_id)
        return list(defaults) if defaults else None

    def is_favorite_league(self, sport_id: int, tour_name: str) -> bool:
        """True, если лига в избранных для вида спорта (None = все лиги)."""
        from match_store import _league_allowed

        leagues = self.leagues_for_sport(sport_id)
        if leagues is None:
            return True
        return _league_allowed(tour_name or "", leagues)

    @classmethod
    def from_env(cls) -> "DeluxSettings":
        auto_sports = os.environ.get("DELUX_SPORTS_AUTO", "1,3,4,6")
        sports = [int(x.strip()) for x in auto_sports.split(",") if x.strip()]

        leagues_by_sport: Dict[int, Optional[List[str]]] = {}
        for sport_id in sports:
            raw = os.environ.get(f"DELUX_LEAGUES_{sport_id}", "").strip()
            if raw:
                leagues_by_sport[sport_id] = _parse_leagues(raw)

        football_leagues = _parse_leagues(os.environ.get("DELUX_LEAGUES", ""))
        if 1 not in leagues_by_sport:
            leagues_by_sport[1] = football_leagues
        for sport_id in sports:
            if sport_id in leagues_by_sport:
                continue
            defaults = DEFAULT_LEAGUES_BY_SPORT.get(sport_id)
            if defaults:
                leagues_by_sport[sport_id] = list(defaults)

        return cls(
            sport=int(os.environ.get("DELUX_SPORT", "1")),
            source=int(os.environ.get("DELUX_SOURCE", "2")),
            tz_base=int(os.environ.get("DELUX_TZ_BASE", "16")),
            dayzone_base=int(os.environ.get("DELUX_DAYZONE_BASE", "8")),
            time_offset=int(os.environ.get("DELUX_TIME_OFFSET", "10")),
            leagues=football_leagues,
            leagues_by_sport=leagues_by_sport,
            sports_auto=sports or list(ALL_SPORTS),
            use_excel_io=_env_bool("DELUX_USE_EXCEL", False),
            calc_backend=os.environ.get("CALC_BACKEND", "python").strip().lower(),
            formula_pure_eval=_env_bool("FORMULA_PURE_EVAL", True),
            calc_workbook=os.environ.get("CALC_WORKBOOK", os.environ.get("EXCEL_FILENAME", "")),
            database_path=os.environ.get("DATABASE_PATH", "matches.db"),
            min_tour_games=int(os.environ.get("DELUX_MIN_TOUR_GAMES", "5") or "5"),
        )
