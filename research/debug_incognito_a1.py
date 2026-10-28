"""Debug A1/I2/I3/I4/I5/I7/I8/I9/I10/I11 for match 238n0PMk."""
import json
from pathlib import Path

d = json.load(open('data/formula_graph.json', 'r', encoding='utf-8'))
nodes = d.get('nodes', {})

print("=== Incognito DATA A1, I2, I3, I4, I5, I7, I8, I9, I10, I11 ===")
for addr in ['A1', 'I2', 'I3', 'I4', 'I5', 'I7', 'I8', 'I9', 'I10', 'I11']:
    k = f'Incognito DATA!{addr}'
    node = nodes.get(k, {})
    formula = node.get('formula') or 'N/A'
    print(f"{k}: {formula[:200]}")
