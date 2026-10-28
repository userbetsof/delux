"""Debug G16/G17/L16/L17 for match 238n0PMk."""
import json
from pathlib import Path

d = json.load(open('data/formula_graph.json', 'r', encoding='utf-8'))
nodes = d.get('nodes', {})

print("=== Incognito DATA G16, G17, G20, G21, G24, G25, G28, G29 ===")
for addr in ['G16', 'G17', 'G20', 'G21', 'G24', 'G25', 'G28', 'G29']:
    k = f'Incognito DATA!{addr}'
    node = nodes.get(k, {})
    formula = node.get('formula') or 'N/A'
    print(f"{k}: {formula[:200]}")

print("\n=== Incognito DATA L16, L17, L20, L21, L24, L25, L28, L29 ===")
for addr in ['L16', 'L17', 'L20', 'L21', 'L24', 'L25', 'L28', 'L29']:
    k = f'Incognito DATA!{addr}'
    node = nodes.get(k, {})
    formula = node.get('formula') or 'N/A'
    print(f"{k}: {formula[:200]}")
