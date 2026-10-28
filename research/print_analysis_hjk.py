import json
from pathlib import Path

d = json.load(open('data/formula_graph.json', 'r', encoding='utf-8'))
nodes = d.get('nodes', {})

# Find what Analysis!H24/J24/K24 reference
print("=== Analysis sheet H24-K26 ===")
for k, v in sorted(nodes.items()):
    if 'Анализ' in k and any(f'{c}{r}' in k for c in ['H','J','K'] for r in [24,25,26]):
        formula = v.get('formula') or 'N/A'
        print(f"{k}: {formula[:200]}")

# Find all cells referencing Table!M26/M27/M28
print("\n=== Cells referencing Table!M26/M27/M28 ===")
for k, v in sorted(nodes.items()):
    formula = v.get('formula') or ''
    if 'Таблица!M26' in formula or 'Таблица!M27' in formula or 'Таблица!M28' in formula:
        print(f"{k}: {formula[:200]}")

# Find what Mill sheet references
print("\n=== Mill sheet cells referencing Table ===")
for k, v in sorted(nodes.items()):
    if 'Mill' in k:
        formula = v.get('formula') or ''
        if 'Таблица' in formula:
            print(f"{k}: {formula[:200]}")
