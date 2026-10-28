import json
from pathlib import Path

d = json.load(open('data/formula_graph.json', 'r', encoding='utf-8'))
nodes = d.get('nodes', {})

print("=== Cells related to 5Match ===")
for k, v in sorted(nodes.items()):
    formula = v.get('formula', '')
    if formula and ('M26' in formula or 'M27' in formula or 'M28' in formula or 'M30' in formula or 'M31' in formula or 'M32' in formula):
        print(f"{k}: {formula[:150]}")
