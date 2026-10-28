"""Debug P16/P20/P24/P28 for match 238n0PMk."""
import json
from pathlib import Path

d = json.load(open('data/formula_graph.json', 'r', encoding='utf-8'))
nodes = d.get('nodes', {})

print("=== Incognito DATA P16, P20, P24, P28, Q16, Q20, Q24, Q28, R16, R20, R24, R28 ===")
for addr in ['P16', 'P20', 'P24', 'P28', 'Q16', 'Q20', 'Q24', 'Q28', 'R16', 'R20', 'R24', 'R28']:
    k = f'Incognito DATA!{addr}'
    node = nodes.get(k, {})
    formula = node.get('formula') or 'N/A'
    print(f"{k}: {formula[:200]}")

# Also check W16, W21, W28
print("\n=== Incognito DATA W16, W21, W28 ===")
for addr in ['W16', 'W21', 'W28']:
    k = f'Incognito DATA!{addr}'
    node = nodes.get(k, {})
    formula = node.get('formula') or 'N/A'
    print(f"{k}: {formula[:200]}")
