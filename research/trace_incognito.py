import json

data = json.load(open('data/formulas_cache.json', encoding='utf-8'))
inc = data.get('sheets', {}).get('Incognito DATA', {})

# Проследить цепочку для S6 (=T32+T34), T6 (=U32+T34), U6 (=V32+T34)
print('=== Цепочка для S6/T6/U6 (подстратегия 0) ===')
for a in ('T32', 'T34', 'U32', 'U34', 'V32', 'V34'):
    print(f'Incognito DATA!{a}: {inc.get(a)}')

print()
print('=== Цепочка для W6/X6/Y6 (подстратегия 1) ===')
for a in ('W13', 'X13', 'Y13', 'Z11'):
    print(f'Incognito DATA!{a}: {inc.get(a)}')
