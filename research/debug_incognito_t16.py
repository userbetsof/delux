"""Debug Incognito DATA T16/T21/T28 etc for match 238n0PMk."""
import json
from pathlib import Path

d = json.load(open('data/formula_graph.json', 'r', encoding='utf-8'))
nodes = d.get('nodes', {})

print("=== Incognito DATA T16, T21, T28, U16, U21, U28, V16, V21, V28, W31 ===")
for addr in ['T16', 'T21', 'T28', 'U16', 'U21', 'U28', 'V16', 'V21', 'V28', 'W31']:
    k = f'Incognito DATA!{addr}'
    node = nodes.get(k, {})
    formula = node.get('formula') or 'N/A'
    print(f"{k}: {formula[:200]}")
