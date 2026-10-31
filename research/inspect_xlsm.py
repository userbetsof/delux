"""Осмотр .xlsm: листы, формулы, VBA-макросы.

Показывает, что можно прочитать без запуска Excel:
  - список листов и их размер
  - количество формул на листе
  - наличие VBA-проекта и его модули
"""

import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

path = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else r"C:\papki\work\bets\delux\DeluX_IncoProrok_new.xlsm"
)

if not path.is_file():
    print(f"[-] нет файла: {path}")
    raise SystemExit(1)

print(f"файл: {path.name} ({path.stat().st_size/1024/1024:.1f} МБ)")

with zipfile.ZipFile(path) as z:
    names = z.namelist()

    # VBA
    vba = [n for n in names if n.startswith("xl/vbaProject")]
    print(f"\nVBA: {'да' if vba else 'нет'}")
    for n in vba:
        print(f"  {n} ({z.getinfo(n).file_size} байт)")

    # Листы
    sheets = sorted(n for n in names if n.startswith("xl/worksheets/sheet"))
    print(f"\nлистов: {len(sheets)}")
    for n in sheets:
        data = z.read(n).decode("utf-8", errors="replace")
        formulas = data.count("<f>")
        dim = ""
        if "<dimension ref=" in data:
            start = data.index("<dimension ref=") + len("<dimension ref=")
            dim = data[start : data.index('"', start + 1)]
        print(f"  {n:32} формул {formulas:6}  диапазон {dim}")

    # Общий подсчёт формул
    total_f = 0
    for n in sheets:
        total_f += z.read(n).decode("utf-8", errors="replace").count("<f>")
    print(f"\nвсего формул в книге: {total_f}")
