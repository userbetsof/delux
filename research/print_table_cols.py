import json
from pathlib import Path
from collections import defaultdict

d = json.load(open('data/formula_graph.json', 'r', encoding='utf-8'))
nodes = d.get('nodes', {})

table_cells = {}
for k, v in nodes.items():
    if 'Таблица' in k:
        table_cells[k] = v.get('formula') or 'N/A'

# Group by column
cols = defaultdict(list)
for k in table_cells:
    addr = k.split('!', 1)[1] if '!' in k else k
    col = ''
    for ch in addr:
        if ch.isalpha():
            col += ch
        else:
            break
    cols[col].append(k)

print("=== Columns in Table sheet formula_graph ===")
for col in sorted(cols.keys()):
    print(f"  {col}: {len(cols[col])} cells, rows: {sorted([int(''.join([c for c in cols[col][0].split('!',1)[1].split(col)[1] if c.isdigit()]))])[:3]}...")

# Check if M column exists
print(f"\n=== M column exists: {'M' in cols} ===")
if 'M' in cols:
    print(f"M cells: {cols['M'][:10]}")

# Check what columns have formulas (not N/A)
print("\n=== Columns with actual formulas (not N/A) ===")
for col in sorted(cols.keys()):
    formulas = [k for k in cols[col] if table_cells[k] != 'N/A']
    if formulas:
        print(f"  {col}: {len(formulas)} formulas")
        for k in formulas[:3]:
            print(f"    {k}: {table_cells[k][:120]}")
