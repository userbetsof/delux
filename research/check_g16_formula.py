"""Check if G16 has a formula in formula_graph."""
import json
from pathlib import Path

d = json.load(open('data/formula_graph.json', 'r', encoding='utf-8'))
nodes = d.get('nodes', {})

print("=== Incognito DATA G16 ===")
k = 'Incognito DATA!G16'
node = nodes.get(k, {})
formula = node.get('formula') or 'N/A'
print(f"{k}: {formula[:200]}")

# Check if G16 is in the formula_graph at all
print(f"\nG16 in nodes: {k in nodes}")
print(f"Formula: {formula}")
