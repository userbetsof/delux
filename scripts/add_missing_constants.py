"""Добавить в formulas_cache.json константы, которых там нет.

Проблема: лист «Графики» содержит таблицу голов в виде ЧИСЕЛ (столбцы
AK/AL и блок $AK$30:$AM$37). Кэш формул их не содержит, поэтому
VLOOKUP(AK42,...) получает None и возвращает первую строку для всех
голов — из-за этого 5Match p даёт одинаковые вероятности.

Скрипт читает книгу, находит ячейки-константы и дописывает недостающие
в кэш как значения (строки без «=»). Существующие формулы не трогает.

    py -3 scripts/add_missing_constants.py --dry-run
    py -3 scripts/add_missing_constants.py
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

CACHE = ROOT / "data" / "formulas_cache.json"


def sheet_files(z: zipfile.ZipFile) -> dict[str, str]:
    """Имя листа -> путь XML внутри книги."""
    wb = z.read("xl/workbook.xml").decode("utf-8", errors="replace")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8", errors="replace")
    rel_map = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    out = {}
    for name, rid in re.findall(
        r'<sheet[^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', wb
    ):
        tgt = rel_map.get(rid, "")
        if tgt:
            out[name] = "xl/" + tgt.lstrip("/").replace("xl/", "", 1)
    return out


def load_shared_strings(z: zipfile.ZipFile) -> list[str]:
    """Таблица общих строк книги (t="s" в ячейках — индекс в ней)."""
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    ss = z.read("xl/sharedStrings.xml").decode("utf-8", errors="replace")
    out = []
    for si in re.findall(r"<si>(.*?)</si>", ss, re.S):
        out.append("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S)))
    return out


def read_constants(
    z: zipfile.ZipFile, path: str, shared: list[str]
) -> dict[str, object]:
    """Ячейки без формул: числа И текст.

    Текст важен: Очные!A1 = «Гавр», и от него зависит VLOOKUP в Mill.
    Раньше брались только числа, поэтому подобные ячейки оставались
    пустыми и VLOOKUP давал #N/A.
    """
    out: dict[str, object] = {}
    # Два формата ячеек: <c ...><v>7</v></c> и самозакрытая <c .../>.
    pattern = re.compile(
        r'<c r="([A-Z]+\d+)"([^>]*?)(?:/>|>(.*?)</c>)', re.S
    )
    with z.open(path) as fh:
        data = fh.read().decode("utf-8", errors="replace")

    for m in pattern.finditer(data):
        ref, attrs, body = m.group(1), m.group(2), m.group(3) or ""
        if "<f" in body:
            continue
        v = re.search(r"<v>(.*?)</v>", body, re.S)
        if not v:
            continue
        raw = v.group(1)
        if 't="s"' in attrs:
            # ссылка на sharedStrings
            try:
                out[ref] = shared[int(raw)]
            except (ValueError, IndexError):
                continue
            continue
        try:
            out[ref] = float(raw)
        except ValueError:
            if raw:
                out[ref] = raw
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsm", default=str(ROOT / "backups" / "DeluX_IncoProrok_new.xlsm"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    xlsm = Path(args.xlsm)
    if not xlsm.is_file():
        print(f"[-] нет книги: {xlsm}")
        return 1

    cache = json.load(open(CACHE, encoding="utf-8"))
    sheets = cache.setdefault("sheets", {})

    total = 0
    # Обрабатываем только листы с расчётными константами. IncoData
    # занимает 64 МБ и тянется минутами — для вероятностей он не нужен.
    ONLY = ("Графики", "Таблица", "Очные", "ОчныеДГ", "Форма")

    with zipfile.ZipFile(xlsm) as z:
        shared = load_shared_strings(z)
        for sheet, path in sheet_files(z).items():
            if sheet not in ONLY:
                continue
            constants = read_constants(z, path, shared)
            if not constants:
                continue
            target = sheets.setdefault(sheet, {})
            added = 0
            for ref, val in constants.items():
                if ref in target:
                    continue
                # формат: значение без «=» = константа
                target[ref] = val
                added += 1
            if added:
                print(f"  {sheet}: +{added}")
                total += added

    print()
    print(f"добавлено констант: {total}")

    if args.dry_run:
        print("[dry-run] кэш не изменён")
        return 0
    if not total:
        print("нечего добавлять")
        return 0

    backup = CACHE.with_suffix(".json.bak2")
    shutil.copy2(CACHE, backup)
    print(f"резервная копия: {backup.name}")

    CACHE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"записано: {CACHE.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
