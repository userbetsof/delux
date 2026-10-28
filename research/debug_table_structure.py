"""Debug Table sheet structure for match 238n0PMk."""
import json
from pathlib import Path

d = json.load(open('data/formula_graph.json', 'r', encoding='utf-8'))
nodes = d.get('nodes', {})

print("=== Table sheet A1-I1 (headers) ===")
for addr in ['A1', 'B1', 'C1', 'D1', 'E1', 'F1', 'G1', 'H1', 'I1']:
    k = f'Таблица!{addr}'
    node = nodes.get(k, {})
    formula = node.get('formula') or 'N/A'
    print(f"{k}: {formula[:200]}")

# Check what column B contains
print("\n=== Table sheet B2-B20 ===")
for addr in [f'B{r}' for r in range(2, 21)]:
    k = f'Таблица!{addr}'
    node = nodes.get(k, {})
    formula = node.get('formula') or 'N/A'
    print(f"{k}: {formula[:200]}")
