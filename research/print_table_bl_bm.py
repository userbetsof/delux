import json
from pathlib import Path

d = json.load(open('data/formula_graph.json', 'r', encoding='utf-8'))
nodes = d.get('nodes', {})

print("=== Table sheet BL/BM/BN cells (26-32) ===")
for k, v in sorted(nodes.items()):
    if 'Таблица' in k and any(f'{col}{r}' in k for col in ['BL','BM','BN'] for r in range(24, 35)):
        formula = v.get('formula') or 'N/A'
        print(f"{k}: {formula[:200]}")

print("\n=== Table sheet M24-M32 ===")
for k, v in sorted(nodes.items()):
    if 'Таблица' in k and any(f'M{r}' in k for r in range(24, 33)):
        formula = v.get('formula') or 'N/A'
        print(f"{k}: {formula[:200]}")

print("\n=== Table sheet all M* cells ===")
for k, v in sorted(nodes.items()):
    if 'Таблица' in k and '!M' in k:
        formula = v.get('formula') or 'N/A'
        print(f"{k}: {formula[:200]}")
