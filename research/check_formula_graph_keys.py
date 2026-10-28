"""Check formula_graph key format."""
import json
from pathlib import Path

d = json.load(open('data/formula_graph.json', 'r', encoding='utf-8'))
nodes = d.get('nodes', {})

# Check a few keys
print("=== Sample keys in formula_graph ===")
count = 0
for k in sorted(nodes.keys()):
    if 'Incognito DATA' in k:
        print(f"  {k}")
        count += 1
        if count >= 10:
            break
