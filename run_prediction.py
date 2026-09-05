import argparse
import os
import sqlite3
import sys
import win32com.client
import openpyxl
from dotenv import load_dotenv

load_dotenv()

DATABASE_PATH = os.environ.get('DATABASE_PATH', 'matches.db')
EXCEL_FILENAME = os.environ.get('EXCEL_FILENAME', 'DeluX_IncoProrok_mvp.xlsm')

from settings import DeluxSettings

# Избранные лиги берутся из .env (DELUX_LEAGUES / DELUX_LEAGUES_4 / DELUX_LEAGUES_3).
# Пустой fallback — все лиги (как раньше при SELECTED_LEAGUES = []).


def _favorite_league_tokens() -> list[str]:
    cfg = DeluxSettings.from_env()
    tokens: list[str] = []
    for sport_id in cfg.sports_auto or [1, 3, 4, 6]:
        leagues = cfg.leagues_for_sport(sport_id)
        if not leagues:
            continue
        for name in leagues:
            if name and name not in tokens:
                tokens.append(name)
    return tokens


SELECTED_LEAGUES = _favorite_league_tokens()


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_existing_match_ids():
    """Возвращает список ID матчей, которые уже сохранены в БД."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT match_id FROM matches")
        rows = cursor.fetchall()
        conn.close()
        return {row['match_id'] for row in rows}
    except Exception as e:
        print(f"[!] Oshibka pri poluchenii suschestvuyushchih matchey iz BD: {e}")
        return set()


def get_matches_from_excel():
    """Читает список матчей из листа 'Список' Excel файла."""
    matches = []
    try:
        wb = openpyxl.load_workbook(EXCEL_FILENAME, read_only=True, data_only=True)
        if "Список" not in wb.sheetnames:
            print("[-] List 'Spisok' ne nayden v Excel faile!")
            return []
        
        sheet = wb["Список"]
        max_row = sheet.max_row
        for r in range(2, max_row + 1):
            match_id = sheet.cell(row=r, column=5).value
            league = sheet.cell(row=r, column=1).value
            if match_id and str(match_id).strip():
                matches.append({
                    'row': r,
                    'match_id': str(match_id).strip(),
                    'league': str(league).strip() if league else '',
                    'date': sheet.cell(row=r, column=2).value,
                    'home': sheet.cell(row=r, column=3).value,
                    'away': sheet.cell(row=r, column=4).value,
                })
        wb.close()
    except Exception as e:
        print(f"[-] Oshibka pri chtenii spiska matchey iz Excel: {e}")
    return matches


def run_prediction_for_match(xl, wb, match_id, row_idx):
    """Выполняет прогнозирование для конкретного матча по его ID и индексу строки."""
    try:
        ws_list = wb.Worksheets("Список")
        ws_list.Select()
        ws_list.Cells(row_idx, "I").Select()
        
        print(f"[*] Zapusk analiza dlya matcha {match_id}...")
        xl.Run("getGame", match_id)
        
        # Чтение результатов прогноза из листа 'Анализ'
        ws_anal = wb.Worksheets("Анализ")
        s13 = ws_anal.Range("S13").Value
        o10 = ws_anal.Range("O10").Value
        x24 = ws_anal.Range("X24").Value
        
        # Проверка на ошибку Excel (в win32com ошибки возвращаются как отрицательные int)
        if isinstance(s13, int) and s13 < 0:
            print(f"[!] Oshibka rascheta formul dlya matcha {match_id} (S13 vernul kod oshibki {s13})")
            return False
            
        print(f"[+] Prognoz uspeshno sohranen v BD dlya matcha {match_id}!")
        print(f"   * Prognoz NTB (S13): {s13}")
        print(f"   * Prognoz Betalone (O10): {o10}")
        print(f"   * Prognoz Sniper (X24): {x24}")
        return True
    except Exception as e:
        print(f"[-] Isklyuchenie pri analize matcha {match_id}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Automatizaciya prognozirovaniya DeluX IncoProrok")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--match-id", type=str, help="ID konkretnogo matcha dlya analiza")
    group.add_argument("--new", action="store_true", help="Analizirovat' tol'ko novye matchi")
    group.add_argument("--all", action="store_true", help="Analizirovat' vse matchi")
    
    args = parser.parse_args()
    
    wb_path = os.path.abspath(EXCEL_FILENAME)
    if not os.path.exists(wb_path):
        print(f"[-] Fail {EXCEL_FILENAME} ne nayden!")
        sys.exit(1)
        
    print("[*] Chtenie matchey iz Excel...")
    excel_matches = get_matches_from_excel()
    if not excel_matches:
        print("[-] Spisok matchey pust!")
        sys.exit(1)
        
    print(f"[+] Naydeno {len(excel_matches)} matchey v Excel.")
    
    # Определение списка матчей для обработки
    to_process = []
    if args.match_id:
        target = args.match_id.strip()
        to_process = [m for m in excel_matches if m['match_id'] == target]
        if not to_process:
            print(f"[-] Match s ID {target} ne nayden v spiske!")
            sys.exit(1)
    elif args.new:
        existing_ids = get_existing_match_ids()
        to_process = [m for m in excel_matches if m['match_id'] not in existing_ids]
        print(f"[*] Iz nih novyh: {len(to_process)} matchey.")
    elif args.all:
        to_process = excel_matches
        print(f"[*] Vsego dlya obrabotki: {len(to_process)} matchey.")
        
    # Фильтрация по избранным лигам (из .env / DeluxSettings)
    if SELECTED_LEAGUES:
        print(f"[*] Primenenie fil'tra izbrannyh lig: {SELECTED_LEAGUES}")
        filtered = []
        for m in to_process:
            match_league = (m.get("league") or "").strip()
            name = match_league.casefold()
            if any(fav.strip().casefold() in name for fav in SELECTED_LEAGUES if fav.strip()):
                filtered.append(m)
        to_process = filtered
        print(f"[+] Posle fil'tracii ostalos': {len(to_process)} matchey.")
        
    if not to_process:
        print("[+] Net matchey dlya obrabotki posle primeneniya fil'trov.")
        sys.exit(0)
        
    # Запуск Excel
    print("[*] Zapusk Microsoft Excel...")
    try:
        os.system("taskkill /f /im excel.exe >nul 2>&1")
    except Exception:
        pass
        
    xl = win32com.client.Dispatch("Excel.Application")
    xl.Visible = True
    xl.DisplayAlerts = True
    xl.ScreenUpdating = False
    
    try:
        print(f"[*] Otkrytie knigi {EXCEL_FILENAME}...")
        wb = xl.Workbooks.Open(wb_path)
        
        success_count = 0
        for idx, match in enumerate(to_process, 1):
            print(f"\n[{idx}/{len(to_process)}] Obrabotka matcha {match['match_id']} (Liga: {match['league']})")
            success = run_prediction_for_match(xl, wb, match['match_id'], match['row'])
            if success:
                success_count += 1
                
        print(f"\n[+] Obrabotka zavershena! Uspeshno obrabotano: {success_count} iz {len(to_process)}")
        
        # Сохранение книги
        print("[*] Sohranenie izmeneniy v knige Excel...")
        try:
            wb.Save()
            wb.Close(True)
        except Exception as save_err:
            print(f"[-] Oshibka pri sohranenii knigi: {save_err}")
            try:
                wb.Close(False)
            except Exception:
                pass
    except Exception as e:
        print(f"[-] Oshibka vo vremya raboty s Excel: {e}")
    finally:
        print("[*] Zakrytie Excel...")
        try:
            xl.Quit()
        except Exception:
            pass
        print("[*] Excel uspeshno zakryt.")


if __name__ == "__main__":
    main()
