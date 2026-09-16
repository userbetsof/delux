import glob
for f in glob.glob("*.bas"):
    with open(f, "r", encoding="utf-8", errors="ignore") as file:
        for i, line in enumerate(file, 1):
            if "Workbook_Open" in line or "Auto_Open" in line:
                print(f"{f}:{i}: {line.strip()}")
