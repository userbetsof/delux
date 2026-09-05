"""Имена листов Excel (unicode-safe defaults + .env override)."""
import os

from dotenv import load_dotenv

load_dotenv()


def _sheet(name: str, default: str) -> str:
    return os.environ.get(name, default)


SHEET_START = _sheet("SHEET_START", "\u0421\u0442\u0430\u0440\u0442")
SHEET_LIST = _sheet("SHEET_LIST", "\u0421\u043f\u0438\u0441\u043e\u043a")
SHEET_ANALYSIS = _sheet("SHEET_ANALYSIS", "\u0410\u043d\u0430\u043b\u0438\u0437")
SHEET_CALC = _sheet("SHEET_CALC", "\u0420\u0430\u0441\u0447\u0435\u0442\u044b")
SHEET_H2H = _sheet("SHEET_H2H", "\u041e\u0447\u043d\u044b\u0435")
SHEET_H2H_HOME = _sheet("SHEET_H2H_HOME", "\u041e\u0447\u043d\u044b\u0435\u0414\u0413")
SHEET_HOME = _sheet("SHEET_HOME", "\u0414\u043e\u043c\u0430")
SHEET_HOME_HOME = _sheet("SHEET_HOME_HOME", "\u0414\u043e\u043c\u0430\u0414\u043e\u043c\u0430")
SHEET_HOME_AWAY = _sheet("SHEET_HOME_AWAY", "\u0414\u043e\u043c\u0430\u0413\u043e\u0441\u0442\u0438")
SHEET_AWAY = _sheet("SHEET_AWAY", "\u0413\u043e\u0441\u0442\u0438")
SHEET_AWAY_HOME = _sheet("SHEET_AWAY_HOME", "\u0413\u043e\u0441\u0442\u0438\u0414\u043e\u043c\u0430")
SHEET_AWAY_AWAY = _sheet("SHEET_AWAY_AWAY", "\u0413\u043e\u0441\u0442\u0438\u0413\u043e\u0441\u0442\u0438")
SHEET_TABLE = _sheet("SHEET_TABLE", "\u0422\u0430\u0431\u043b\u0438\u0446\u0430")
SHEET_FORM = _sheet("SHEET_FORM", "\u0424\u043e\u0440\u043c\u0430")
SHEET_ODDS = _sheet("SHEET_ODDS", "\u041a\u043e\u044d\u0444\u0444\u0438\u0446\u0438\u0435\u043d\u0442\u044b")
SHEET_GRAFIKI = _sheet("SHEET_GRAFIKI", "\u0413\u0440\u0430\u0444\u0438\u043a\u0438")

# Листы с формулами, зависящими от матча (пересчитываются в pure_eval)
DYNAMIC_SHEETS = (
    SHEET_CALC,
    SHEET_GRAFIKI,
    SHEET_ANALYSIS,
    SHEET_TABLE,
    SHEET_FORM,
    SHEET_H2H,
    SHEET_H2H_HOME,
    SHEET_HOME,
    SHEET_HOME_HOME,
    SHEET_HOME_AWAY,
    SHEET_AWAY,
    SHEET_AWAY_HOME,
    SHEET_AWAY_AWAY,
    "IncoData",
    "Mill",
    "Elizabet2",
    "Incognito DATA",
    "Valui",
    "Poisson",
    "Beta8",
)

# Константы без формул (если есть) — заполняются lookups.db
STATIC_SHEETS = ()
