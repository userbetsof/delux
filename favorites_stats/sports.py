"""Имена видов спорта DeluX / Flashscore."""

from __future__ import annotations

SPORT_NAMES: dict[int, str] = {
    1: "Футбол",
    3: "Баскетбол",
    4: "Хоккей",
    6: "Бейсбол",
}


def sport_label(sport_id: int) -> str:
    return SPORT_NAMES.get(int(sport_id), f"Спорт {sport_id}")
