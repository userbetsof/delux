"""Звуковое уведомление: нужно ввести имя команды (dogs / WhoScored).

Зачем: при анализе сезона скрипт останавливается и ждёт ввода, а оператор
может быть занят другим. Звук привлекает внимание.

На Windows используется winsound (стандартная библиотека, без зависимостей).
Вне Windows или при недоступности звука — тихий откат на терминальный BEL.
Управление: переменная окружения DELUX_SILENT=1 отключает звук.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

# Частоты/длительности (мс) для узнаваемого «двойного сигнала».
_ATTENTION_PATTERN: tuple[tuple[int, int], ...] = (
    (880, 140),
    (0, 60),  # пауза
    (1175, 200),
)


def sound_enabled() -> bool:
    """Звук включён, если не задан DELUX_SILENT."""
    value = os.environ.get("DELUX_SILENT", "").strip().lower()
    return value not in ("1", "true", "yes", "on")


def _beep_windows(pattern: tuple[tuple[int, int], ...]) -> bool:
    try:
        import winsound  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001
        return False
    try:
        for freq, duration in pattern:
            if freq <= 0:
                # winsound не умеет паузу — «спим» через Beep(0)? нет,
                # проще пропустить: пауза не критична.
                continue
            winsound.Beep(freq, duration)
        return True
    except Exception:  # noqa: BLE001
        # Beep может быть недоступен (нет звуковой карты / удалённый сеанс)
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            return True
        except Exception:  # noqa: BLE001
            return False


def _fallback_bell() -> None:
    """Терминальный BEL — работает в большинстве консолей."""
    try:
        sys.stdout.write("\a")
        sys.stdout.flush()
    except Exception:  # noqa: BLE001
        pass


def alert_attention(times: int = 1, *, reason: str = "") -> None:
    """Проиграть звук «требуется ввод».

    times: сколько раз повторить сигнал (для настойчивости при нескольких
    командах подряд).
    reason: необязательный текст для лога (сам звук ничего не печатает).
    """
    if not sound_enabled():
        return
    played = False
    pattern = _ATTENTION_PATTERN * max(1, times)
    if sys.platform.startswith("win"):
        played = _beep_windows(pattern)
    if not played:
        # На не-Windows или без звуковой карты — хотя бы BEL.
        for _ in range(max(1, times)):
            _fallback_bell()
        played = True
    if reason and played:
        pass  # текст печатает вызывающий код; здесь только звук


def alert_attention_async(times: int = 1) -> None:
    """Неблокирующий вариант: звук в фоне, чтобы не задерживать ввод."""
    try:
        import threading

        threading.Thread(
            target=alert_attention, args=(times,), daemon=True
        ).start()
    except Exception:  # noqa: BLE001
        alert_attention(times)
