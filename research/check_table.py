import json
from pathlib import Path

p = Path('data/formula_graph.json')
d = json.load(open(p, encoding='utf-8'))
nodes = d.get('nodes', {})

# Find all Table sheet nodes
table_nodes = {k: v for k, v in nodes.items() if 'Таблица' in k}
print(f"Table nodes: {len(table_nodes)}")

# Check what M26-M32 formulas are
for k, v in sorted(table_nodes.items()):
    formula = v.get('formula')
    if formula and any(f'M{r}' in k for r in range(20, 40)):
        print(f"{k}: {formula}")

# Check what M26 depends on: =SUM(AO42:AO69)/100
# Let's find AO42:AO69
print("\n=== AO cells ===")
for k, v in sorted(table_nodes.items()):
    formula = v.get('formula')
    if formula and 'AO' in k:
        print(f"{k}: {formula}")
