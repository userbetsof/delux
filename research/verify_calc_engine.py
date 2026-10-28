"""Verify calc_engine.py M26-M32 logic."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from calc_engine import _find_team_in_table, _team_rates, _table_rows

# Test data from Штутгарт vs Боруссия М
home_rows = [
    ['1', 'Бавария', '3', '3', '0', '0', '10', '2', '9'],
    ['2', 'РБ Лейпциг', '3', '3', '0', '0', '8', '3', '9'],
    ['3', 'Фрайбург', '3', '3', '0', '0', '7', '2', '9'],
    ['4', 'Байер', '3', '3', '0', '0', '9', '4', '9'],
    ['5', 'Боруссия Д', '3', '2', '1', '0', '6', '3', '7'],
    ['6', 'Штутгарт', '2', '1', '0', '1', '4', '3', '3'],
    ['7', 'Вольфсбург', '3', '1', '1', '1', '5', '5', '4'],
    ['8', 'Боруссия М', '3', '0', '0', '3', '2', '8', '0'],
]

away_rows = [
    ['1', 'Майнц', '3', '3', '0', '0', '8', '3', '9'],
    ['2', 'Боруссия Д', '3', '2', '1', '0', '7', '4', '7'],
    ['3', 'Бавария', '3', '1', '2', '0', '6', '4', '5'],
    ['4', 'Байер', '3', '1', '1', '1', '5', '5', '4'],
    ['5', 'Фрайбург', '3', '1', '1', '1', '4', '4', '4'],
    ['6', 'Штутгарт', '4', '1', '0', '3', '5', '8', '3'],
    ['7', 'Вольфсбург', '3', '1', '0', '2', '4', '5', '3'],
    ['8', 'Боруссия М', '3', '0', '0', '3', '2', '8', '0'],
]

print("=== Home team (Штутгарт) ===")
home_team_row = _find_team_in_table(home_rows, 'Штутгарт')
print(f"Found: {home_team_row}")
if home_team_row:
    rates = _team_rates(home_team_row)
    print(f"Rates: {rates}")
    if rates:
        print(f"  win={rates[0]*100:.2f}%  draw={rates[1]*100:.2f}%  away={rates[2]*100:.2f}%")
        print(f"  sum={sum(rates)*100:.2f}%")

print("\n=== Away team (Боруссия М) ===")
away_team_row = _find_team_in_table(away_rows, 'Боруссия М')
print(f"Found: {away_team_row}")
if away_team_row:
    rates = _team_rates(away_team_row)
    print(f"Rates: {rates}")
    if rates:
        print(f"  win={rates[0]*100:.2f}%  draw={rates[1]*100:.2f}%  away={rates[2]*100:.2f}%")
        print(f"  sum={sum(rates)*100:.2f}%")
