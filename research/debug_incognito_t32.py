"""Debug Incognito DATA T32/T34/U32/V32 for match 238n0PMk."""
import json
from pathlib import Path

d = json.load(open('data/formula_graph.json', 'r', encoding='utf-8'))
nodes = d.get('nodes', {})

print("=== Incognito DATA T32, T34, U32, V32 ===")
for addr in ['T32', 'T34', 'U32', 'V32']:
    k = f'Incognito DATA!{addr}'
    node = nodes.get(k, {})
    formula = node.get('formula') or 'N/A'
    print(f"{k}: {formula[:200]}")
