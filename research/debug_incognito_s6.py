"""Debug Incognito DATA S6/T6/U6 for match 238n0PMk."""
import json
from pathlib import Path

d = json.load(open('data/formula_graph.json', 'r', encoding='utf-8'))
nodes = d.get('nodes', {})

print("=== Incognito DATA S6, T6, U6 ===")
for addr in ['S6', 'T6', 'U6']:
    k = f'Incognito DATA!{addr}'
    node = nodes.get(k, {})
    formula = node.get('formula') or 'N/A'
    print(f"{k}: {formula[:200]}")

# Check what S6 depends on
print("\n=== Cells referencing Incognito DATA!S6 ===")
for k, v in sorted(nodes.items()):
    formula = v.get('formula') or ''
    if 'Incognito DATA!S6' in formula:
        print(f"{k}: {formula[:200]}")
