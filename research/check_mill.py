import json
from pathlib import Path

p = Path('data/formula_graph.json')
d = json.load(open(p, encoding='utf-8'))
nodes = d.get('nodes', {})

# Check Mill sheet formulas
print("=== Mill sheet key cells ===")
for k, v in nodes.items():
    if 'Mill' in k:
        formula = v.get('formula') or 'N/A'
        print(f"{k}: {formula[:150]}")

# Check what's in Analysis for strategies
print("\n=== Analysis sheet strategy cells ===")
for k, v in nodes.items():
    if 'Анализ' in k:
        formula = v.get('formula') or 'N/A'
        print(f"{k}: {formula[:200]}")
