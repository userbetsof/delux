"""Сравнить константы Графики (AK/AL/AK30:AM37) между книгой и кэшем.

В Excel столбцы AK/AL содержат ЧИСЛА голов (не формулы). Кэш формул их
не хранит, поэтому движок читает None → VLOOKUP(None,...) возвращает
первое совпадение, и все вероятности получаются одинаковыми.
"""

import json
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

XLSM = r"C:\papki\work\bets\delux\backups\DeluX_IncoProrok_new.xlsm"
CACHE = r"C:\papki\work\bets\delux\data\formulas_cache.json"

# 1) константы из книги
with zipfile.ZipFile(XLSM) as z:
    d = z.read("xl/worksheets/sheet12.xml").decode("utf-8", errors="replace")

book = {}
for m in re.finditer(r'<c r="([A-Z]+\d+)"([^>]*)>(.*?)</c>', d, re.S):
    ref, attrs, body = m.groups()
    if "<f" in body:
        continue
    v = re.search(r"<v>(.*?)</v>", body, re.S)
    if not v:
        continue
    try:
        book[ref] = float(v.group(1))
    except ValueError:
        continue

# 2) кэш
cache = json.load(open(CACHE, encoding="utf-8"))
g = cache["sheets"]["Графики"]

# 3) какие константы книги отсутствуют в кэше
missing = []
for ref, val in book.items():
    if ref not in g:
        missing.append((ref, val))

print(f"констант в книге (лист Графики): {len(book)}")
print(f"ячеек в кэше: {len(g)}")
print(f"отсутствуют в кэше: {len(missing)}")
print()

# сгруппируем по столбцу
from collections import Counter

cols = Counter(re.match(r"([A-Z]+)", ref).group(1) for ref, _ in missing)
print("по столбцам:", dict(sorted(cols.items())))
print()

print("примеры отсутствующих (первые 10):")
for ref, val in missing[:10]:
    print(f"  {ref} = {val}")

# проверим ключевые для 5Match p
print()
print("ключевые ячейки:")
for ref in ("AK42", "AL42", "AK73", "AL73", "AK30", "AL30", "AM30"):
    in_book = ref in book
    in_cache = ref in g
    print(f"  {ref}: в книге={in_book}, в кэше={in_cache}")
