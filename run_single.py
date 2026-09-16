"""Запуск анализа матча Q9s7530B через Excel."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from match_analysis import run_cli
from db import create_database

if __name__ == "__main__":
    create_database()
    
    match_id = "Q9s7530B"
    print(f"=== Анализ матча {match_id} ===")
    
    try:
        run_cli(
            workbook="",  # путь к Excel берётся из env
            match_id=match_id,
        )
        print(f"\n[+] Анализ {match_id} завершён успешно")
    except Exception as e:
        print(f"\n[-] Ошибка: {e}")
        import traceback
        traceback.print_exc()
