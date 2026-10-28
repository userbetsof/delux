import json
from pathlib import Path

d = json.load(open('data/formula_graph.json', 'r', encoding='utf-8'))
nodes = d.get('nodes', {})

print("=== Analysis sheet H8-K26 ===")
for k, v in sorted(nodes.items()):
    if 'Анализ' in k and any(f'{c}{r}' in k for c in ['H','J','K'] for r in [8,10,12,14,16,18,20,22,24,26]):
        formula = v.get('formula') or 'N/A'
        print(f"{k}: {formula[:200]}")
