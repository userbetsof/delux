import json
from pathlib import Path

p = Path('data/formula_graph.json')
d = json.load(open(p, encoding='utf-8'))
nodes = d.get('nodes', {})

# Check Incognito DATA formulas
print("=== Incognito DATA formulas ===")
for k, v in nodes.items():
    if 'Incognito DATA' in k:
        print(f"{k}: {v.get('formula')}")
