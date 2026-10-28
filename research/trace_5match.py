"""Trace 5Match dependencies from Analysis sheet."""
import json
from pathlib import Path

p = Path('data/formula_graph.json')
d = json.load(open(p, encoding='utf-8'))
nodes = d.get('nodes', {})

# 5Match row is H26/J26/K26 in Analysis
# From screenshot: 17%/60%/23%
# H26=M26, J26=M28, K26=M27 (from formula_graph)

print("=== Analysis H26/J26/K26 ===")
for addr in ['H26', 'J26', 'K26']:
    k = f'Анализ!{addr}'
    node = nodes.get(k, {})
    formula = node.get('formula')
    print(f"{k}: {formula}")

# M26 = SUM(AO42:AO69)/100 — это из Table sheet
# Но Table sheet не имеет формул в formula_graph — данные заполняются напрямую

# Let's check what M26/M27/M28 really are
print("\n=== Table sheet M26/M27/M28 formulas ===")
for addr in ['M26', 'M27', 'M28', 'M30', 'M31', 'M32']:
    k = f'Таблица!{addr}'
    node = nodes.get(k, {})
    formula = node.get('formula')
    print(f"{k}: {formula}")

# Check what AO42:AO69 are
print("\n=== Table AO cells (if any) ===")
ao_nodes = {k: v for k, v in nodes.items() if 'Таблица' in k and 'AO' in k}
print(f"AO nodes: {len(ao_nodes)}")
for k, v in sorted(ao_nodes.items())[:10]:
    print(f"{k}: {v.get('formula')}")

# Check what BM26/BM27/BM28 are (VLOOKUP results)
print("\n=== Table BM26-BM32 ===")
for addr in ['BM26', 'BM27', 'BM28', 'BM30', 'BM31', 'BM32']:
    k = f'Таблица!{addr}'
    node = nodes.get(k, {})
    formula = node.get('formula')
    print(f"{k}: {formula}")

# Check BK26-BK32 (VLOOKUP lookup values)
print("\n=== Table BK26-BK32 ===")
for addr in ['BK26', 'BK27', 'BK28', 'BK30', 'BK31', 'BK32']:
    k = f'Таблица!{addr}'
    node = nodes.get(k, {})
    formula = node.get('formula')
    print(f"{k}: {formula}")
