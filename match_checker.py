"""
Проверка результатов матчей: раз в минуту запрос к API за незавершёнными матчами
и обновление результатов в БД.
DEBUG_MODE: только вывод получаемых/заполняемых данных без записи в БД.
"""
import os
import sqlite3
import time
from typing import Any, Optional

import requests
from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    """Читает булево значение из переменной окружения."""
    v = os.environ.get(name, str(default)).strip().lower()
    return v in ("1", "true", "yes")


# Настройки из .env
MATCH_CHECKER_DEBUG_MODE = _env_bool("MATCH_CHECKER_DEBUG_MODE", False)
DATABASE_PATH = os.environ.get("DATABASE_PATH", "matches.db")
MATCH_API_URL = os.environ.get("MATCH_API_URL", "http://127.0.0.1:5000")
MATCH_API_POLL_INTERVAL_SEC = int(os.environ.get("MATCH_API_POLL_INTERVAL_SEC", "60"))


class MatchResultChecker:
    """
    Каждые N секунд запрашивает у API список незавершённых матчей
    и обновляет в БД: match_status, score_home, score_away, minute, segment, profit.
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        database_path: Optional[str] = None,
        debug_mode: Optional[bool] = None,
        poll_interval_sec: Optional[int] = None,
    ):
        self.api_url = (api_url or MATCH_API_URL).rstrip("/")
        self.database_path = database_path or DATABASE_PATH
        self.debug_mode = debug_mode if debug_mode is not None else MATCH_CHECKER_DEBUG_MODE
        self.poll_interval_sec = poll_interval_sec or MATCH_API_POLL_INTERVAL_SEC
        self._running = False

    def _fetch_unfinished_matches(self) -> list[dict[str, Any]]:
        """Запрос к моковому API: возвращает список незавершённых матчей с полями результата."""
        url = f"{self.api_url}/unfinished-matches"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "matches" in data:
                return data["matches"]
            return []
        except requests.RequestException as e:
            print(f"Ошибка запроса к API {url}: {e}")
            return []
        except (ValueError, KeyError) as e:
            print(f"Ошибка разбора ответа API: {e}")
            return []

    def _normalize_match(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Приводит поля одного матча из API к виду для БД."""
        match_id = str(raw.get("match_id", raw.get("id", "")))
        return {
            "match_id": match_id,
            "match_status": str(raw.get("match_status", "Не начался")).strip() or "Не начался",
            "score_home": int(raw["score_home"]) if raw.get("score_home") is not None else 0,
            "score_away": int(raw["score_away"]) if raw.get("score_away") is not None else 0,
            "minute": str(raw.get("minute", "90+")).strip() or "90+",
            "segment": str(raw.get("segment", "0")).strip() or "0",
            "profit": float(raw["profit"]) if raw.get("profit") is not None else 0.0,
        }

    def _update_match_in_db(self, conn: sqlite3.Connection, m: dict[str, Any]) -> bool:
        """Обновляет одну запись матча в БД по match_id."""
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE matches
            SET match_status = ?, score_home = ?, score_away = ?, minute = ?, segment = ?, profit = ?
            WHERE match_id = ?
            """,
            (
                m["match_status"],
                m["score_home"],
                m["score_away"],
                m["minute"],
                m["segment"],
                m["profit"],
                m["match_id"],
            ),
        )
        return cursor.rowcount > 0

    def _print_debug(self, matches: list[dict[str, Any]], message: str = "Данные для заполнения") -> None:
        """Вывод в консоль для режима отладки."""
        print("\n" + "=" * 70)
        print(f"🔍 MATCH_CHECKER DEBUG: {message}")
        print("=" * 70)
        if not matches:
            print("  (список пуст)")
        for i, m in enumerate(matches, 1):
            print(f"  [{i}] match_id={m.get('match_id')} | {m.get('score_home')}:{m.get('score_away')} | "
                  f"min={m.get('minute')} seg={m.get('segment')} | status={m.get('match_status')} | profit={m.get('profit')}")
        print("=" * 70)
        if self.debug_mode:
            print("✅ DEBUG_MODE: запись в БД не выполнялась")
        print()

    def run_once(self) -> int:
        """
        Один цикл: запрос к API и обновление БД (или только вывод в debug_mode).
        Returns: количество обновлённых записей в БД (0 в debug_mode).
        """
        raw_list = self._fetch_unfinished_matches()
        matches = [self._normalize_match(r) for r in raw_list if str(r.get("match_id", r.get("id", ""))).strip()]

        if self.debug_mode:
            self._print_debug(matches, "Получены незавершённые матчи (без записи в БД)")
            return 0

        updated = 0
        try:
            conn = sqlite3.connect(self.database_path)
            for m in matches:
                if self._update_match_in_db(conn, m):
                    updated += 1
            conn.commit()
            conn.close()
            if matches:
                print(f"Обновлено записей в БД: {updated} из {len(matches)}")
        except Exception as e:
            print(f"Ошибка обновления БД: {e}")

        return updated

    def run_loop(self) -> None:
        """Запуск бесконечного цикла: опрос API каждые poll_interval_sec секунд."""
        self._running = True
        print(f"MatchResultChecker запущен. API={self.api_url}, интервал={self.poll_interval_sec} с, DEBUG={self.debug_mode}")
        while self._running:
            self.run_once()
            time.sleep(self.poll_interval_sec)

    def stop(self) -> None:
        """Остановка цикла run_loop."""
        self._running = False


if __name__ == "__main__":
    checker = MatchResultChecker()
    try:
        checker.run_loop()
    except KeyboardInterrupt:
        checker.stop()
        print("Остановлено по Ctrl+C")
