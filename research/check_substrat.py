"""Check what Elizabet2 and 5Match depend on."""
import json
from pathlib import Path

p = Path('data/formula_graph.json')
d = json.load(open(p, encoding='utf-8'))
nodes = d.get('nodes', {})

# Elizabet2 formulas
print("=== Elizabet2 key formulas ===")
for k, v in nodes.items():
    if 'Elizabet2' in k and v.get('formula'):
        formula = v['formula']
        if any(cell in formula for cell in ['H2','I2','J2','K2','H3','I3','J3','K3','H4','I4','J4','K4','H5','I5','J5','K5']):
            print(f"{k}: {formula[:200]}")

# Poisson formulas
print("\n=== Poisson key formulas ===")
for k, v in nodes.items():
    if 'Poisson' in k and v.get('formula'):
        formula = v['formula']
        if any(cell in formula for cell in ['B13','C13','D13']):
            print(f"{k}: {formula[:200]}")

# Valui formulas
print("\n=== Valui key formulas ===")
for k, v in nodes.items():
    if 'Valui' in k and v.get('formula'):
        formula = v['formula']
        if any(cell in formula for cell in ['M41']):
            print(f"{k}: {formula[:200]}")
