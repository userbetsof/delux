"""Кэш ответов фидов на диск.

Проблема: канал до Flashscore отдаёт 12-15 КБ/с и рвётся. Один матч требует
десятки запросов, поэтому пересчёт 392 матчей растягивается на часы.

Решение: сохраняем каждый скачанный фид в файл. При повторном запросе того
же URL отдаём локальную копию — ноль обращений к сети.

Кэш нужен в двух случаях:
  1. Повторный пересчёт тех же матчей (данные те же).
  2. Прерывание: уже скачанное остаётся и используется при возобновлении.

Формат: data/feed_cache/<sha1 url>.txt — обычный текст, читается глазами.
Управление:
    DELUX_FEED_CACHE=0        выключить кэш
    DELUX_FEED_CACHE_DIR=...  другой каталог
    --clear                   очистить кэш
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parent
DEFAULT_DIR = ROOT / "data" / "feed_cache"


def cache_enabled() -> bool:
    value = (os.environ.get("DELUX_FEED_CACHE") or "").strip().lower()
    return value not in ("0", "false", "no", "off")


def cache_dir() -> Path:
    custom = (os.environ.get("DELUX_FEED_CACHE_DIR") or "").strip()
    return Path(custom) if custom else DEFAULT_DIR


def _path_for(url: str) -> Path:
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return cache_dir() / f"{key}.txt"


def _index_path() -> Path:
    """Файл-индекс: sha1 -> исходный URL (чтобы понимать, что в кэше)."""
    return cache_dir() / "_index.tsv"


def get(url: str) -> Optional[str]:
    """Вернуть закэшированный ответ или None."""
    path = _path_for(url)
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return text or None


def put(url: str, text: str) -> None:
    """Сохранить ответ. Ошибки записи не должны ломать анализ."""
    if not text:
        return
    try:
        folder = cache_dir()
        folder.mkdir(parents=True, exist_ok=True)
        _path_for(url).write_text(text, encoding="utf-8")
        with _index_path().open("a", encoding="utf-8") as fh:
            fh.write(f"{_path_for(url).stem}\t{url}\n")
    except OSError:
        pass


def stats() -> dict:
    """Сколько файлов и байт в кэше."""
    folder = cache_dir()
    if not folder.is_dir():
        return {"files": 0, "bytes": 0, "dir": str(folder)}
    files = [p for p in folder.glob("*.txt") if p.is_file()]
    return {
        "files": len(files),
        "bytes": sum(p.stat().st_size for p in files),
        "dir": str(folder),
    }


def clear() -> int:
    """Удалить кэш. Возвращает число удалённых файлов."""
    folder = cache_dir()
    if not folder.is_dir():
        return 0
    count = 0
    for path in folder.iterdir():
        try:
            if path.is_file():
                path.unlink()
                count += 1
            elif path.is_dir():
                shutil.rmtree(path)
        except OSError:
            continue
    return count


def install(fetch_fn: Callable) -> Callable:
    """Обернуть fetch_feed кэшем.

    Модули проекта импортируют fetch_feed по имени и из разных мест
    (flashscore_feed, analysis_data, team_history, …), поэтому обёртку
    надо ставить во все места, где имя уже импортировано.
    """
    if not cache_enabled():
        return fetch_fn

    def cached(url: str, *args, **kwargs):
        hit = get(url)
        if hit is not None:
            return hit
        text = fetch_fn(url, *args, **kwargs)
        put(url, text)
        return text

    # Подменяем во всех загруженных модулях, где есть fetch_feed.
    import sys as _sys

    for module in list(_sys.modules.values()):
        if module is None:
            continue
        if getattr(module, "fetch_feed", None) is fetch_fn:
            module.fetch_feed = cached
    return cached


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Кэш фидов Flashscore")
    parser.add_argument("--stats", action="store_true", help="Показать размер кэша")
    parser.add_argument("--clear", action="store_true", help="Очистить кэш")
    parser.add_argument(
        "--list", action="store_true", help="Список закэшированных URL"
    )
    args = parser.parse_args()

    if args.clear:
        n = clear()
        print(f"удалено файлов: {n}")
        return 0
    if args.list:
        index = _index_path()
        if not index.is_file():
            print("кэш пуст")
            return 0
        with index.open(encoding="utf-8") as fh:
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) == 2:
                    print(parts[1])
        return 0

    st = stats()
    print(f"каталог: {st['dir']}")
    print(f"файлов:  {st['files']}")
    print(f"размер:  {st['bytes']/1024/1024:.1f} МБ")
    print(f"включён: {cache_enabled()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
