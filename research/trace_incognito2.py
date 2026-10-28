import json

data = json.load(open('data/formulas_cache.json', encoding='utf-8'))
inc = data.get('sheets', {}).get('Incognito DATA', {})

# углубимся: T16/T21/T28, G16/L16, W12/Y12/Z12
print('=== T16/T21/T28 ===')
for a in ('T16', 'T21', 'T28'):
    print(f'  {a}: {inc.get(a)}')
print('=== G16, G20, L16, L20 ===')
for a in ('G16', 'G20', 'L16', 'L20'):
    print(f'  {a}: {inc.get(a)}')
print('=== W12, Y12, Z12 ===')
for a in ('W12', 'Y12', 'Z12'):
    print(f'  {a}: {inc.get(a)}')
print('=== W31 ===')
print('  W31:', inc.get('W31'))
