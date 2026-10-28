"""Find 5Match and 5Match p strategies in formula graph."""
import json
from pathlib import Path

p = Path('data/formula_graph.json')
d = json.load(open(p, encoding='utf-8'))
nodes = d.get('nodes', {})

# Search for M26/M28/M30/M31/M32 (5Match formulas from screenshot)
print("=== Analysis sheet M26-M32 ===")
for k, v in nodes.items():
    if 'Анализ' in k and any(f'M{r}' in k for r in range(20, 40)):
        formula = v.get('formula') or 'N/A'
        print(f"{k}: {formula[:200]}")

# Search for M26/M27/M28/M30/M31/M32 in all sheets
print("\n=== All M26-M32 cells ===")
for k, v in nodes.items():
    if any(f'M{r}' in k for r in [26, 27, 28, 30, 31, 32]):
        formula = v.get('formula') or 'N/A'
        print(f"{k}: {formula[:200]}")
