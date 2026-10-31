import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

MID = "ncRVhYJ7"

# эталон из Excel (лист Анализ): хозяева / ничья / гости
EXCEL = {
    "ср взвеш": (4, 9, 88),
    "mill": (22, -49, 127),
    "Mini Vini": (2, 29, 69),
    "Elizabet": (8, 17, 75),
    "5Match p": (25, 18, 57),
    "5Match": (14, 8, 77),
    "5 д/г+оч": (None, 13, 77),
}

# движок (последний прогон)
ENGINE = {
    "1 пр": (2.6, 13.6, 83.8),
    "2 пр": (2.6, 28.2, 69.2),
    "de lux": (3.4, 21.2, 75.4),
    "poisson": (10.0, 13.0, 76.9),
    "ср взвеш": (3.5, 8.8, 87.7),
    "mill": (0.0, -26.9, 126.9),
    "Mini Vini": (2.0, 29.3, 68.7),
    "Elizabet": (7.9, 17.1, 75.1),
    "5Match p": (27.5, 6.9, 27.5),
    "5Match": (14.2, 8.3, 77.5),
}

print(f"{'стратегия':11} {'движок':>18} {'Excel':>16}  итог")
print("-" * 60)
ok = 0
for name, eng in ENGINE.items():
    ex = EXCEL.get(name)
    if not ex or ex[0] is None:
        print(f"{name:11} {eng[0]:6.1f}{eng[1]:6.1f}{eng[2]:6.1f}   {'?':>16}  —")
        continue
    m = all(abs(eng[i] - ex[i]) <= 1.5 for i in range(3))
    if m:
        ok += 1
    print(
        f"{name:11} {eng[0]:6.1f}{eng[1]:6.1f}{eng[2]:6.1f}   "
        f"{ex[0]:5}{ex[1]:5}{ex[2]:5}  {'OK' if m else 'РАСХОД'}"
    )
print()
print(f"совпало {ok} из {len(EXCEL) - 1}")
