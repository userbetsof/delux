"""Debug B2/C2/D2/B3/C3/D3 etc for match 238n0PMk."""
import json
from pathlib import Path

d = json.load(open('data/formula_graph.json', 'r', encoding='utf-8'))
nodes = d.get('nodes', {})

print("=== Incognito DATA B2, C2, D2, B3, C3, D3, B4, C4, D4, B5, C5, D5 ===")
for addr in ['B2', 'C2', 'D2', 'B3', 'C3', 'D3', 'B4', 'C4', 'D4', 'B5', 'C5', 'D5']:
    k = f'Incognito DATA!{addr}'
    node = nodes.get(k, {})
    formula = node.get('formula') or 'N/A'
    print(f"{k}: {formula[:200]}")

print("\n=== Incognito DATA B8, C8, D8, B9, C9, D9, B10, C10, D10, B11, C11, D11 ===")
for addr in ['B8', 'C8', 'D8', 'B9', 'C9', 'D9', 'B10', 'C10', 'D10', 'B11', 'C11', 'D11']:
    k = f'Incognito DATA!{addr}'
    node = nodes.get(k, {})
    formula = node.get('formula') or 'N/A'
    print(f"{k}: {formula[:200]}")
