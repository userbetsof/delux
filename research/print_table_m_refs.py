import json

d = json.load(open('data/formula_graph.json', 'r', encoding='utf-8'))
nodes = d.get('nodes', {})

# Find all cells that reference Table!M
print("=== Cells referencing Table!M* ===")
for k, v in sorted(nodes.items()):
    formula = v.get('formula') or ''
    if 'Таблица!M' in formula:
        print(f"{k}: {formula[:200]}")

# Find Elizabet2 sheet formulas
print("\n=== Elizabet2 sheet formulas ===")
for k, v in sorted(nodes.items()):
    if 'Elizabet2' in k:
        formula = v.get('formula') or 'N/A'
        print(f"{k}: {formula[:200]}")
