"""Find what 5Match needs from Table sheet."""
import json
from pathlib import Path

p = Path('data/formula_graph.json')
d = json.load(open(p, encoding='utf-8'))
nodes = d.get('nodes', {})

# 5Match formulas: H26=M26, J26=M28, K26=M27 (from formula_graph)
# M26/M27/M28 are from Table sheet
# Let's trace what M26 depends on

print("=== Table sheet formulas for M26/M27/M28 ===")
for k, v in nodes.items():
    if 'Таблица' in k and any(f'M{r}' in k for r in [26, 27, 28, 30, 31, 32]):
        formula = v.get('formula') or 'N/A'
        print(f"{k}: {formula[:200]}")

# Also check what M26/M27/M28 depend on via AO columns
print("\n=== Table sheet AO columns (for M26/M27/M28) ===")
for k, v in nodes.items():
    if 'Таблица' in k and 'AO' in k:
        formula = v.get('formula') or 'N/A'
        print(f"{k}: {formula[:200]}")

# Check what BK26/BK27/BK28 are (for BM26/BM27/BM28 VLOOKUP)
print("\n=== Table sheet BK columns ===")
for k, v in nodes.items():
    if 'Таблица' in k and any(f'BK{r}' in k for r in range(20, 40)):
        formula = v.get('formula') or 'N/A'
        print(f"{k}: {formula[:200]}")

# Check what AZ5:BB12 contains (VLOOKUP source for BM26)
print("\n=== Table sheet AZ:BB range ===")
for k, v in nodes.items():
    if 'Таблица' in k and any(f'{col}{r}' in k for col in ['AZ','BA','BB'] for r in range(1, 20)):
        formula = v.get('formula') or 'N/A'
        if formula != 'N/A':
            print(f"{k}: {formula[:200]}")
