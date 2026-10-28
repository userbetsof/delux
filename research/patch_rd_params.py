import io
import sys

sys.stdout.reconfigure(encoding="utf-8")

path = r"C:\papki\work\bets\delux\ratings.py"
src = io.open(path, encoding="utf-8").read()

pairs = (
    ("home_new", "home_new_rd", "home_vol"),
    ("away_new", "away_new_rd", "away_vol"),
)

for name, rd, vol in pairs:
    old = "(\n                " + name + ",\n                " + vol + ",\n"
    new = (
        "(\n                "
        + name
        + ",\n                "
        + rd
        + ",\n                "
        + vol
        + ",\n"
    )
    n = src.count(old)
    print(f"{name}: найдено {n}")
    src = src.replace(old, new)

io.open(path, "w", encoding="utf-8").write(src)
print("done")
