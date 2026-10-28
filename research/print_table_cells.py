import json
from pathlib import Path

d = json.load(open('data/formula_graph.json', 'r', encoding='utf-8'))
nodes = d.get('nodes', {})

print("=== All Table sheet cells in formula_graph ===")
table_cells = {}
for k, v in nodes.items():
    if 'Таблица' in k:
        table_cells[k] = v.get('formula') or 'N/A'

print(f"Total Table cells in graph: {len(table_cells)}")
# Show first 30
for k, v in sorted(table_cells.items())[:30]:
    print(f"  {k}: {v[:150]}")

# Group by column
from collections import defaultdict
cols = defaultdict(list)
for k in table_cells:
    # extract column letter
    addr = k.split('!', 1)[1] if '!' in k else k
    col = ''
    for ch in addr:
        if ch.isalpha():
            col += ch
        else:
            break
    cols[col].append(k)

print("\n=== Cells by column ===")
for col in sorted(cols.keys()):
    print(f"  {col}: {len(cols[col])} cells")
    for k in sorted(cols[col])[:5]:
        print(f"    {k}: {table_cells[k][:100]}")
