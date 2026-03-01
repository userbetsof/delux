import sqlite3
import os
import pandas as pd
import openpyxl
from dotenv import load_dotenv

from telegram_client import TelegramNotifier

load_dotenv()


def _env_bool(name, default=False):
    """Читает булево значение из переменной окружения."""
    v = os.environ.get(name, str(default)).strip().lower()
    return v in ('1', 'true', 'yes')


# Настройки из .env (токены, пути, названия листов)
DEBUG_MODE = _env_bool('DEBUG_MODE', False)
DATABASE_PATH = os.environ.get('DATABASE_PATH', 'matches.db')
SHEET_ANALYSIS = os.environ.get('SHEET_ANALYSIS', 'Анализ')
SHEET_ARCHIVE = os.environ.get('SHEET_ARCHIVE', 'Архив')
SHEET_ODDS = os.environ.get('SHEET_ODDS', 'Коэффициенты')
EXCEL_FILENAME = os.environ.get('EXCEL_FILENAME', 'DeluX_IncoProrok_new.xlsm')
EXCEL_FALLBACK_PATH = os.environ.get('EXCEL_FALLBACK_PATH', r'C:\papki\work\Bets\DeluX_IncoProrok_new.xlsm')

def create_database():
    """Создание базы данных и таблиц"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Таблица для стран
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS countries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(50) UNIQUE NOT NULL
    )
    ''')
    
    # Таблица для лиг
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS leagues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) NOT NULL,
        country_id INTEGER,
        FOREIGN KEY (country_id) REFERENCES countries(id),
        UNIQUE(name, country_id)
    )
    ''')
    
    # Таблица для команд
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) UNIQUE NOT NULL
    )
    ''')
    
    # Таблица для матчей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id VARCHAR(8) UNIQUE NOT NULL,
        match_date TEXT NOT NULL,
        league_id INTEGER,
        home_team_id INTEGER,
        away_team_id INTEGER,
        prediction VARCHAR(10),
        match_status VARCHAR(20) DEFAULT "Не начался",
        profit DECIMAL(10,2) DEFAULT 0.00,
        minute VARCHAR(5) DEFAULT "90+",
        segment VARCHAR(20) DEFAULT "0",
        score_home INTEGER DEFAULT 0,
        score_away INTEGER DEFAULT 0,
        sport INTEGER DEFAULT 1 CHECK (sport BETWEEN 1 AND 99),
        FOREIGN KEY (league_id) REFERENCES leagues(id),
        FOREIGN KEY (home_team_id) REFERENCES teams(id),
        FOREIGN KEY (away_team_id) REFERENCES teams(id)
    )
    ''')
    
    # Таблица для коэффициентов (связь с матчами) - обновленная версия
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS odds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id VARCHAR(8) NOT NULL,
        home_win_odds VARCHAR(10),
        draw_odds VARCHAR(10),
        away_win_odds VARCHAR(10),
        odds_1x VARCHAR(10),      -- Добавляем 1x
        odds_12 VARCHAR(10),      -- Добавляем 12
        odds_2x VARCHAR(10),      -- Добавляем 2x
        FOREIGN KEY (match_id) REFERENCES matches(match_id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS goal_probabilities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id VARCHAR(8) NOT NULL,
        home_goals_0 DECIMAL(5,2),   -- Вероятность 0 голов хозяев
        home_goals_1 DECIMAL(5,2),   -- Вероятность 1 гола хозяев
        home_goals_2 DECIMAL(5,2),   -- Вероятность 2 голов хозяев
        home_goals_3 DECIMAL(5,2),   -- Вероятность 3 голов хозяев
        home_goals_4 DECIMAL(5,2),   -- Вероятность 4 голов хозяев
        home_goals_5 DECIMAL(5,2),   -- Вероятность 5+ голов хозяев
        away_goals_0 DECIMAL(5,2),   -- Вероятность 0 голов гостей
        away_goals_1 DECIMAL(5,2),   -- Вероятность 1 гола гостей
        away_goals_2 DECIMAL(5,2),   -- Вероятность 2 голов гостей
        away_goals_3 DECIMAL(5,2),   -- Вероятность 3 голов гостей
        away_goals_4 DECIMAL(5,2),   -- Вероятность 4 голов гостей
        away_goals_5 DECIMAL(5,2),   -- Вероятность 5+ голов гостей
        FOREIGN KEY (match_id) REFERENCES matches(match_id),
        UNIQUE(match_id)  -- Одна запись вероятностей голов на матч
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sub_strategies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy_name VARCHAR(50) UNIQUE NOT NULL,
        description TEXT
    )
    ''')

    # Вероятности исходов по 10 подстратегиям (3x10)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS outcome_probabilities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id VARCHAR(8) NOT NULL,
        strategy_id INTEGER NOT NULL,
        home_win_prob DECIMAL(5,2),  -- Вероятность победы хозяев (%)
        draw_prob DECIMAL(5,2),       -- Вероятность ничьи (%)
        away_win_prob DECIMAL(5,2),   -- Вероятность победы гостей (%)
        FOREIGN KEY (match_id) REFERENCES matches(match_id),
        FOREIGN KEY (strategy_id) REFERENCES sub_strategies(id),
        UNIQUE(match_id, strategy_id)  -- Уникальная комбинация матча и стратегии
    )
    ''')

    conn.commit()
    return conn

def parse_league(league_str):
    """Разделение строки лиги на страну и название лиги"""
    if ': ' in league_str:
        country, league = league_str.split(': ', 1)
        return country.strip(), league.strip()
    else:
        return 'Unknown', league_str

def insert_or_get_country(cursor, country_name):
    """Добавление страны или получение её ID"""
    cursor.execute('SELECT id FROM countries WHERE name = ?', (country_name,))
    result = cursor.fetchone()
    
    if result:
        return result[0]
    else:
        cursor.execute('INSERT INTO countries (name) VALUES (?)', (country_name,))
        return cursor.lastrowid

def insert_or_get_league(cursor, league_name, country_id):
    """Добавление лиги или получение её ID"""
    cursor.execute('SELECT id FROM leagues WHERE name = ? AND country_id = ?', 
                  (league_name, country_id))
    result = cursor.fetchone()
    
    if result:
        return result[0]
    else:
        cursor.execute('INSERT INTO leagues (name, country_id) VALUES (?, ?)', 
                      (league_name, country_id))
        return cursor.lastrowid

def insert_or_get_team(cursor, team_name):
    """Добавление команды или получение её ID"""
    cursor.execute('SELECT id FROM teams WHERE name = ?', (team_name,))
    result = cursor.fetchone()
    
    if result:
        return result[0]
    else:
        cursor.execute('INSERT INTO teams (name) VALUES (?)', (team_name,))
        return cursor.lastrowid

def insert_match_data(item):
    """Вставка одного матча из данных в базу данных"""
    conn = create_database()
    cursor = conn.cursor()
    
    try:
        # Извлекаем данные
        match_id = str(item.get('id', '')) if 'id' in item else str(item.get('match_id', ''))
        match_date = item.get('match_date', '')
        league_str = item.get('league', '')
        home_team = item.get('home', '')
        away_team = item.get('away', '')
        prediction = item.get('prediction', '')
        home_win_odds = item.get('home_win_odds', '')
        draw_odds = item.get('draw_odds', '')
        away_win_odds = item.get('away_win_odds', '')

        # Прогнозы по стратегиям
        strategy_pred_1 = item.get('strategy_pred_1', '')  # AJ
        strategy_pred_2 = item.get('strategy_pred_2', '')  # AK
        strategy_pred_3 = item.get('strategy_pred_3', '')  # BK

        # Новые коэффициенты
        odds_1x = item.get('1x_odds', '')
        odds_12 = item.get('12_odds', '')
        odds_2x = item.get('2x_odds', '')
        
        # Разделяем лигу на страну и название
        country_name, league_name = parse_league(league_str)
        
        # Получаем или создаем страны, лиги и команды
        country_id = insert_or_get_country(cursor, country_name)
        league_id = insert_or_get_league(cursor, league_name, country_id)
        home_team_id = insert_or_get_team(cursor, home_team)
        away_team_id = insert_or_get_team(cursor, away_team)
        
        # Вставляем матч
        cursor.execute('''
        INSERT OR REPLACE INTO matches 
        (match_id, match_date, league_id, home_team_id, away_team_id, prediction)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (match_id, match_date, league_id, home_team_id, away_team_id, prediction))
        
        # Вставляем коэффициенты (обновленная версия)
        cursor.execute('''
        INSERT OR REPLACE INTO odds 
        (match_id, home_win_odds, draw_odds, away_win_odds, odds_1x, odds_12, odds_2x)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (match_id, home_win_odds, draw_odds, away_win_odds, odds_1x, odds_12, odds_2x))

        # Вставляем прогнозы по стратегиям
        insert_strategy_predictions(conn, match_id, {
            1: strategy_pred_1,
            2: strategy_pred_2,
            3: strategy_pred_3
        })

        conn.commit()
        
        # Выводим статистику
        cursor.execute('SELECT COUNT(*) FROM matches')
        match_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM countries')
        country_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM leagues')
        league_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM teams')
        team_count = cursor.fetchone()[0]
        
        print(f"Матч успешно добавлен в базу данных!")
        print(f"Текущая статистика:")
        print(f"  • Матчи: {match_count}")
        print(f"  • Страны: {country_count}")
        print(f"  • Лиги: {league_count}")
        print(f"  • Команды: {team_count}")
        print(f"  • Доп. коэффициенты: 1x={odds_1x}, 12={odds_12}, 2x={odds_2x}")
        
        return True
        
    except Exception as e:
        print(f"Ошибка при вставке матча: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def insert_strategy_predictions(conn, match_id, strategy_predictions):
    """
    Вставляет прогнозы по стратегиям в таблицу strategy_predictions
    
    strategy_predictions: словарь {strategy_id: prediction}
    где strategy_id: 1, 2, 3 (соответствуют AJ, AK, BK)
    """
    cursor = conn.cursor()
    
    for strategy_id, prediction in strategy_predictions.items():
        if prediction and prediction.strip():  # Проверяем, что прогноз не пустой
            try:
                cursor.execute('''
                INSERT OR REPLACE INTO strategy_predictions 
                (match_id, strategy_id, prediction)
                VALUES (?, ?, ?)
                ''', (match_id, strategy_id, prediction.strip()))
                print(f"    ✅ Прогноз для стратегии ID {strategy_id}: {prediction}")
            except Exception as e:
                print(f"    ❌ Ошибка при вставке прогноза для стратегии ID {strategy_id}: {e}")

def get_merged_cell_value(sheet, cell_address):
    """Получает значение из объединенной ячейки"""
    cell = sheet[cell_address]
    
    # Если ячейка объединена, берем значение из верхней левой ячейки диапазона
    if cell.coordinate in sheet.merged_cells:
        for merged_range in sheet.merged_cells.ranges:
            if cell.coordinate in merged_range:
                # Берем значение из первой ячейки объединенного диапазона
                top_left_cell = sheet.cell(row=merged_range.min_row, column=merged_range.min_col)
                return top_left_cell.value
    return cell.value

def extract_goal_probabilities(sheet):
    """
    Извлекает вероятности голов для хозяев (столбцы V-AA) и гостей (столбцы AI-AN)
    Все ячейки имеют объединение по 2 строки, всего 2 строки данных
    
    Возвращает:
    - home_goals: список вероятностей для хозяев [0,1,2,3,4,5+]
    - away_goals: список вероятностей для гостей [0,1,2,3,4,5+]
    """
    
    # Колонки для хозяев: V=22, W=23, X=24, Y=25, Z=26, AA=27
    home_columns = [22, 23, 24, 25, 26, 27]  # V, W, X, Y, Z, AA
    
    # Колонки для гостей: AI=35, AJ=36, AK=37, AL=38, AM=39, AN=40
    away_columns = [35, 36, 37, 38, 39, 40]  # AI, AJ, AK, AL, AM, AN
    
    # Строки для данных (всего 2 строки, объединенные)
    data_rows = [10, 11]  # Строки 10 и 11
    
    print(f"\n📊 Чтение вероятностей голов:")
    print("=" * 60)
    
    home_goals = []
    away_goals = []
    
    try:
        # Читаем вероятности для хозяев
        print(f"\n🏠 Вероятности голов хозяев (столбцы V-AA):")
        for i, col in enumerate(home_columns):
            # Пробуем прочитать из первой строки объединенного диапазона
            cell_value = sheet.cell(row=data_rows[0], column=col).value
            
            # Если в первой строке пусто, пробуем вторую
            if cell_value is None:
                cell_value = sheet.cell(row=data_rows[1], column=col).value
            
            try:
                prob = float(cell_value) if cell_value is not None else 0
                goal_label = f"{i} голов" if i < 5 else "5+ голов"
                print(f"  • {goal_label:8}: {prob:.4f} ({prob*100:.2f}%)")
                home_goals.append(prob)
            except (ValueError, TypeError):
                print(f"  • {goal_label:8}: Н/Д")
                home_goals.append(0)
        
        # Читаем вероятности для гостей
        print(f"\n🚌 Вероятности голов гостей (столбцы AI-AN):")
        for i, col in enumerate(away_columns):
            # Пробуем прочитать из первой строки объединенного диапазона
            cell_value = sheet.cell(row=data_rows[0], column=col).value
            
            # Если в первой строке пусто, пробуем вторую
            if cell_value is None:
                cell_value = sheet.cell(row=data_rows[1], column=col).value
            
            try:
                prob = float(cell_value) if cell_value is not None else 0
                goal_label = f"{i} голов" if i < 5 else "5+ голов"
                print(f"  • {goal_label:8}: {prob:.4f} ({prob*100:.2f}%)")
                away_goals.append(prob)
            except (ValueError, TypeError):
                print(f"  • {goal_label:8}: Н/Д")
                away_goals.append(0)
        
        # Проверяем суммы вероятностей (должны быть близки к 1.0)
        home_total = sum(home_goals)
        away_total = sum(away_goals)
        
        print(f"\n📈 Проверка сумм:")
        print(f"  • Сумма вероятностей хозяев: {home_total:.4f} ({home_total*100:.2f}%) {'✅' if abs(home_total - 1.0) < 0.05 else '⚠️'}")
        print(f"  • Сумма вероятностей гостей: {away_total:.4f} ({away_total*100:.2f}%) {'✅' if abs(away_total - 1.0) < 0.05 else '⚠️'}")
        
    except Exception as e:
        print(f"❌ Ошибка при чтении вероятностей голов: {e}")
        # В случае ошибки возвращаем нулевые значения
        home_goals = [0] * 6
        away_goals = [0] * 6
    
    print("\n" + "=" * 60)
    return home_goals, away_goals

def insert_goal_probabilities(excel_file_path, match_id):
    """
    Читает вероятности голов из листа "Анализ" и вставляет их в таблицу goal_probabilities
    """
    try:
        # Открываем Excel файл
        wb = openpyxl.load_workbook(excel_file_path, data_only=True)
        
        # Проверяем наличие листа анализа
        if SHEET_ANALYSIS not in wb.sheetnames:
            print(f"❌ Лист '{SHEET_ANALYSIS}' не найден")
            return False
        
        sheet_analysis = wb[SHEET_ANALYSIS]
        
        # Извлекаем вероятности голов
        home_goals, away_goals = extract_goal_probabilities(sheet_analysis)
        
        # В режиме отладки только выводим вероятности, не сохраняем
        if DEBUG_MODE:
            print("\n" + "=" * 70)
            print("🔍 РЕЖИМ ОТЛАДКИ: Вероятности голов НЕ сохраняются в БД")
            print("=" * 70)
            print(f"📊 Данные для матча {match_id}:")
            print("-" * 70)
            
            print("\n🏠 Хозяева (вероятности голов):")
            goals_labels = ['0', '1', '2', '3', '4', '5+']
            for i, prob in enumerate(home_goals):
                print(f"  • {goals_labels[i]:2} голов: {prob:.4f} ({prob*100:.2f}%)")
            
            print("\n🚌 Гости (вероятности голов):")
            for i, prob in enumerate(away_goals):
                print(f"  • {goals_labels[i]:2} голов: {prob:.4f} ({prob*100:.2f}%)")
            
            print("\n" + "=" * 70)
            print("✅ Для сохранения в БД установите DEBUG_MODE = False")
            print("=" * 70)
            
            wb.close()
            return True
        
        # Режим реального сохранения в БД
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # УМНОЖАЕМ НА 100 для сохранения в процентах
        home_goals_percent = [p * 100 for p in home_goals]
        away_goals_percent = [p * 100 for p in away_goals]
        
        try:
            cursor.execute('''
            INSERT OR REPLACE INTO goal_probabilities 
            (match_id, home_goals_0, home_goals_1, home_goals_2, home_goals_3, home_goals_4, home_goals_5,
             away_goals_0, away_goals_1, away_goals_2, away_goals_3, away_goals_4, away_goals_5)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                match_id,
                home_goals_percent[0], home_goals_percent[1], home_goals_percent[2],
                home_goals_percent[3], home_goals_percent[4], home_goals_percent[5],
                away_goals_percent[0], away_goals_percent[1], away_goals_percent[2],
                away_goals_percent[3], away_goals_percent[4], away_goals_percent[5]
            ))
            
            conn.commit()
            print(f"\n✅ Вероятности голов успешно сохранены в БД для матча {match_id}")
            
            # Проверяем сохраненные данные
            cursor.execute('''
            SELECT home_goals_0, home_goals_1, home_goals_2, home_goals_3, home_goals_4, home_goals_5,
                   away_goals_0, away_goals_1, away_goals_2, away_goals_3, away_goals_4, away_goals_5
            FROM goal_probabilities
            WHERE match_id = ?
            ''', (match_id,))
            
            result = cursor.fetchone()
            if result:
                print("\n📊 Проверка сохраненных данных (в процентах):")
                print("-" * 60)
                
                print("Хозяева:")
                for i in range(6):
                    label = f"{i} голов" if i < 5 else "5+ голов"
                    print(f"  • {label:8}: {result[i]:6.2f}%")
                
                print("\nГости:")
                for i in range(6, 12):
                    label = f"{i-6} голов" if i-6 < 5 else "5+ голов"
                    print(f"  • {label:8}: {result[i]:6.2f}%")
                
                home_total = sum(result[:6])
                away_total = sum(result[6:])
                print(f"\nСумма хозяев: {home_total:.2f}% {'✅' if abs(home_total - 100) < 5 else '⚠️'}")
                print(f"Сумма гостей: {away_total:.2f}% {'✅' if abs(away_total - 100) < 5 else '⚠️'}")
            
        except Exception as e:
            print(f"❌ Ошибка при сохранении вероятностей голов: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
            wb.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при обработке данных: {e}")
        import traceback
        traceback.print_exc()
        return False

def extract_probabilities_from_analysis(sheet):
    """
    Извлекает вероятности для 10 подстратегий из листа "Анализ"
    
    Структура листа:
    - Столбцы H-L (колонки 8-12) содержат данные для 10 подстратегий
    - Строки 8-28 содержат данные
    - Для каждой подстратегии:
        * Домашняя команда: объединенные ячейки 2x2 (вероятность победы хозяев)
        * Ничья: 1 колонка x 2 строки (вероятность ничьей)
        * Гостевая команда: объединенные ячейки 2x2 (вероятность победы гостей)
    
    Возвращает значения как ДОЛИ (0-1), а не проценты
    """
    
    probabilities = []
    
    # Фиксированные колонки: H=8, I=9, J=10, K=11, L=12
    columns = [8, 9, 10, 11, 12]  # H, I, J, K, L
    
    # Начальная строка для данных
    start_row = 8
    
    print(f"\n📊 Чтение вероятностей из столбцов H-L (8-12), строки {start_row}-28:")
    print("=" * 60)
    
    # 10 подстратегий (идут последовательно сверху вниз)
    for strategy_idx in range(10):
        # Вычисляем строку для текущей стратегии
        # Каждая стратегия занимает 2 строки (из-за объединенных ячеек)
        current_row = start_row + (strategy_idx * 2)
        
        if current_row + 1 > 28:  # Проверяем, не вышли ли за пределы (макс строка 28)
            print(f"⚠️ Достигнут конец диапазона на стратегии {strategy_idx + 1}")
            break
        
        try:
            print(f"\n📌 Стратегия {strategy_idx + 1} (строки {current_row}-{current_row+1}):")
            
            # Домашняя команда (объединенные ячейки H? : I?+1) - 2x2
            # Используем левую верхнюю ячейку объединенного диапазона
            home_cell_h = sheet.cell(row=current_row, column=8)  # H8, H10, H12, ...
            home_cell_i = sheet.cell(row=current_row, column=9)  # I8, I10, I12, ...
            
            # Объединенные ячейки обычно имеют значение только в верхней левой
            home_prob = home_cell_h.value if home_cell_h.value is not None else home_cell_i.value
            
            # Ничья (ячейки J? и J?+1) - 1 колонка x 2 строки
            draw_cell_top = sheet.cell(row=current_row, column=10)      # J8, J10, J12, ...
            draw_cell_bottom = sheet.cell(row=current_row + 1, column=10)  # J9, J11, J13, ...
            draw_prob = draw_cell_top.value if draw_cell_top.value is not None else draw_cell_bottom.value
            
            # Гостевая команда (объединенные ячейки K? : L?+1) - 2x2
            away_cell_k = sheet.cell(row=current_row, column=11)  # K8, K10, K12, ...
            away_cell_l = sheet.cell(row=current_row, column=12)  # L8, L10, L12, ...
            
            # Объединенные ячейки обычно имеют значение только в верхней левой
            away_prob = away_cell_k.value if away_cell_k.value is not None else away_cell_l.value
            
            # Преобразуем в числа, если возможно
            try:
                home_prob = float(home_prob) if home_prob is not None else 0
                print(f"  • Дома (H{current_row}/I{current_row}): {home_prob:.4f}")
            except (ValueError, TypeError):
                home_prob = 0
                print(f"  • Дома (H{current_row}/I{current_row}): Н/Д")
                
            try:
                draw_prob = float(draw_prob) if draw_prob is not None else 0
                print(f"  • Ничья (J{current_row}/J{current_row+1}): {draw_prob:.4f}")
            except (ValueError, TypeError):
                draw_prob = 0
                print(f"  • Ничья (J{current_row}/J{current_row+1}): Н/Д")
                
            try:
                away_prob = float(away_prob) if away_prob is not None else 0
                print(f"  • Гости (K{current_row}/L{current_row}): {away_prob:.4f}")
            except (ValueError, TypeError):
                away_prob = 0
                print(f"  • Гости (K{current_row}/L{current_row}): Н/Д")
            
            # Проверяем сумму вероятностей (как доли, должно быть близко к 1.0)
            total = home_prob + draw_prob + away_prob
            if abs(total - 1.0) > 0.01:  # Допускаем погрешность в 0.01 (1%)
                print(f"  ⚠️ Сумма долей: {total:.4f} (должна быть ~1.0)")
                print(f"    В процентах: {total*100:.2f}% (должно быть ~100%)")
            else:
                print(f"  ✅ Сумма долей: {total:.4f} (~1.0)")
                print(f"    В процентах: {total*100:.2f}% (~100%)")
            
            probabilities.append({
                'strategy_idx': strategy_idx,
                'home_prob': home_prob,  # Сохраняем как доли (0-1)
                'draw_prob': draw_prob,  # Сохраняем как доли (0-1)
                'away_prob': away_prob,  # Сохраняем как доли (0-1)
                'row': current_row
            })
            
        except Exception as e:
            print(f"❌ Ошибка при чтении стратегии {strategy_idx + 1}: {e}")
            probabilities.append({
                'strategy_idx': strategy_idx,
                'home_prob': 0,
                'draw_prob': 0,
                'away_prob': 0,
                'row': current_row
            })
    
    print("\n" + "=" * 60)
    return probabilities

def insert_outcome_probabilities_from_analysis(excel_file_path, match_id):
    """
    Читает вероятности из листа "Анализ" (столбцы H-L, строки 8-28) 
    и вставляет их в таблицу outcome_probabilities для всех 10 подстратегий
    """
    try:
        # Открываем Excel файл
        wb = openpyxl.load_workbook(excel_file_path, data_only=True)
        
        # Проверяем наличие листа анализа
        if SHEET_ANALYSIS not in wb.sheetnames:
            print(f"❌ Лист '{SHEET_ANALYSIS}' не найден")
            return False
        
        sheet_analysis = wb[SHEET_ANALYSIS]
        
        # Получаем список всех подстратегий из базы данных
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Получаем все подстратегии
        cursor.execute('SELECT id, strategy_name FROM sub_strategies ORDER BY id')
        strategies = cursor.fetchall()
        
        if len(strategies) < 10:
            print(f"⚠️ В базе только {len(strategies)} подстратегий из 10")
            # Добавляем недостающие стратегии, если нужно
            insert_default_strategies()
            # Повторно получаем список стратегий
            cursor.execute('SELECT id, strategy_name FROM sub_strategies ORDER BY id')
            strategies = cursor.fetchall()
        
        # Извлекаем вероятности из листа Анализ
        print(f"\n📊 Чтение вероятностей для матча {match_id}:")
        probabilities = extract_probabilities_from_analysis(sheet_analysis)
        
        # В режиме отладки только выводим вероятности, не сохраняем
        if DEBUG_MODE:
            print("\n" + "=" * 70)
            print("🔍 РЕЖИМ ОТЛАДКИ: Вероятности НЕ сохраняются в БД")
            print("=" * 70)
            print(f"📊 Данные для матча {match_id}:")
            print("-" * 70)
            
            for i, prob_data in enumerate(probabilities):
                if i < len(strategies):
                    strategy_name = strategies[i][1]
                    # Показываем исходные значения (как доли)
                    print(f"\n  📍 {strategy_name} (строки {prob_data['row']}-{prob_data['row']+1}):")
                    print(f"      Исходные значения (доли):")
                    print(f"        Победа хозяев: {prob_data['home_prob']:.4f}")
                    print(f"        Ничья:         {prob_data['draw_prob']:.4f}")
                    print(f"        Победа гостей: {prob_data['away_prob']:.4f}")
                    # Показываем значения в процентах
                    print(f"      В процентах:")
                    print(f"        Победа хозяев: {prob_data['home_prob'] * 100:.2f}%")
                    print(f"        Ничья:         {prob_data['draw_prob'] * 100:.2f}%")
                    print(f"        Победа гостей: {prob_data['away_prob'] * 100:.2f}%")
                    total_doles = prob_data['home_prob'] + prob_data['draw_prob'] + prob_data['away_prob']
                    total_percent = total_doles * 100
                    print(f"      {'✅' if abs(total_doles - 1.0) < 0.01 else '⚠️'} Сумма (доли): {total_doles:.4f}")
                    print(f"      {'✅' if abs(total_percent - 100) < 1 else '⚠️'} Сумма (%):    {total_percent:.2f}%")
            
            print("\n" + "=" * 70)
            print("✅ Для сохранения в БД установите DEBUG_MODE = False")
            print("=" * 70)
            
            conn.close()
            wb.close()
            return True
        
        # Режим реального сохранения в БД
        print("\n💾 Сохранение вероятностей в базу данных...")
        success_count = 0
        for i, prob_data in enumerate(probabilities):
            if i < len(strategies):
                strategy_id = strategies[i][0]
                strategy_name = strategies[i][1]
                
                # УМНОЖАЕМ НА 100 для сохранения в процентах
                home_prob_percent = prob_data['home_prob'] * 100
                draw_prob_percent = prob_data['draw_prob'] * 100
                away_prob_percent = prob_data['away_prob'] * 100
                
                try:
                    cursor.execute('''
                    INSERT OR REPLACE INTO outcome_probabilities 
                    (match_id, strategy_id, home_win_prob, draw_prob, away_win_prob)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (
                        match_id, 
                        strategy_id, 
                        home_prob_percent,
                        draw_prob_percent,
                        away_prob_percent
                    ))
                    success_count += 1
                    print(f"  ✅ {strategy_name}: {home_prob_percent:.2f}% / {draw_prob_percent:.2f}% / {away_prob_percent:.2f}%")
                    
                except Exception as e:
                    print(f"  ❌ Ошибка при вставке для стратегии {strategy_name}: {e}")
        
        conn.commit()
        
        print(f"\n✅ Успешно сохранены вероятности для {success_count} подстратегий")
        
        # Проверяем, что данные сохранились
        cursor.execute('''
        SELECT s.strategy_name, o.home_win_prob, o.draw_prob, o.away_win_prob 
        FROM outcome_probabilities o
        JOIN sub_strategies s ON o.strategy_id = s.id
        WHERE o.match_id = ?
        ORDER BY s.id
        ''', (match_id,))
        
        results = cursor.fetchall()
        if results:
            print("\n📊 Проверка сохраненных данных (в процентах):")
            print("-" * 60)
            for row in results:
                total = row[1] + row[2] + row[3]
                print(f"  • {row[0]:12}: {row[1]:6.2f}% / {row[2]:6.2f}% / {row[3]:6.2f}%")
                print(f"    Сумма: {total:6.2f}% {'✅' if abs(total - 100) < 1 else '⚠️'}")
        
        conn.close()
        wb.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при обработке данных: {e}")
        import traceback
        traceback.print_exc()
        return False
    
def verify_strategies_in_db():
    """Проверяет, что в базе есть все 10 подстратегий"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM sub_strategies')
    count = cursor.fetchone()[0]
    
    if count < 10:
        print(f"⚠️ В базе только {count} подстратегий из 10")
        print("Добавьте недостающие подстратегии:")
        
        # Список имен для 10 подстратегий (замените на ваши реальные названия)
        default_strategies = [
            'sub_strat_1', 'sub_strat_2', 'sub_strat_3', 'sub_strat_4', 'sub_strat_5',
            'sub_strat_6', 'sub_strat_7', 'sub_strat_8', 'sub_strat_9', 'sub_strat_10'
        ]
        
        for i, strat_name in enumerate(default_strategies, 1):
            try:
                cursor.execute('''
                INSERT OR IGNORE INTO sub_strategies (strategy_name, description)
                VALUES (?, ?)
                ''', (strat_name, f'Подстратегия {i}'))
                print(f"  • Добавлена: {strat_name}")
            except:
                pass
        
        conn.commit()
    
    # Показываем все стратегии
    cursor.execute('SELECT id, strategy_name FROM sub_strategies ORDER BY id')
    strategies = cursor.fetchall()
    
    print("\n📋 Стратегии в базе:")
    for strat in strategies:
        print(f"  ID {strat[0]}: {strat[1]}")
    
    conn.close()
    return strategies

def insert_match_data_with_probabilities(item, excel_file_path):
    """
    Вставка данных матча вместе с вероятностями из листа Анализ
    """
    # Сначала вставляем основные данные матча
    success = insert_match_data(item)
    
    if success:
        match_id = str(item.get('id', '')) if 'id' in item else str(item.get('match_id', ''))

        # Вставляем вероятности из листа Анализ
        insert_outcome_probabilities_from_analysis(excel_file_path, match_id)
        
        # Вставляем вероятности голов
        insert_goal_probabilities(excel_file_path, match_id)
    
    return success

# Если вам нужно получить вероятности для конкретной стратегии
def get_strategy_probabilities(match_id, strategy_name):
    """Получает вероятности для конкретной стратегии"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT o.home_win_prob, o.draw_prob, o.away_prob
    FROM outcome_probabilities o
    JOIN sub_strategies s ON o.strategy_id = s.id
    WHERE o.match_id = ? AND s.strategy_name = ?
    ''', (match_id, strategy_name))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'home': result[0],
            'draw': result[1],
            'away': result[2]
        }
    return None

def get_goal_probabilities(match_id):
    """Получает вероятности голов для матча"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT home_goals_0, home_goals_1, home_goals_2, home_goals_3, home_goals_4, home_goals_5,
           away_goals_0, away_goals_1, away_goals_2, away_goals_3, away_goals_4, away_goals_5
    FROM goal_probabilities
    WHERE match_id = ?
    ''', (match_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'home': result[:6],
            'away': result[6:]
        }
    return None

def get_cell_value(sheet, row, column):
    """Безопасное получение значения ячейки"""
    try:
        cell = sheet.cell(row=row, column=column)
        return str(cell.value) if cell.value is not None else ''
    except:
        return ''

def get_column_letter(col_num):
    """Преобразует номер колонки в букву (1 -> A, 2 -> B, etc.)"""
    result = ""
    while col_num > 0:
        col_num -= 1
        result = chr(col_num % 26 + 65) + result
        col_num //= 26
    return result

def read_excel_file(file_path):
    """Чтение данных из Excel файла с использованием только openpyxl"""
    try:
        # Открываем Excel файл
        wb = openpyxl.load_workbook(file_path, data_only=True)
        
        # Проверяем наличие листа архива
        if SHEET_ARCHIVE not in wb.sheetnames:
            print(f"Лист '{SHEET_ARCHIVE}' не найден")
            return None
        
        sheet_archive = wb[SHEET_ARCHIVE]
        
        # Получаем последнюю строку с данными
        max_row = sheet_archive.max_row
        if max_row < 2:  # Если есть только заголовки или пусто
            print(f"Лист '{SHEET_ARCHIVE}' не содержит данных")
            return None
        
        last_row = max_row
        
        # Маппинг колонок: (буква, номер_колонки)
        column_mapping = {
            'A': 1,   # match_date
            'B': 2,   # league
            'C': 3,   # home
            'D': 4,   # away
            'E': 5,   # id
            'AJ': 36, # prediction (A=1, J=10, AJ = 1 + 9*3 = 36)
            'AK': 37, # strategy_pred_1 (AJ + 1)
            'BK': 63, # strategy_pred_2 (проверим: B=2, K=11, BK = 2*26 + 11 = 63)
            'AN': 40, # home_win_odds (A=1, N=14, AN = 1 + 13*3 = 40)
            'AO': 41, # draw_odds
            'AP': 42, # away_win_odds
            'BJ': 62, # sport (A=1, J=10, BJ = 2*26 + 10 = 62)
        }
        
        # Проверяем, есть ли заголовки в первой строке
        has_headers = sheet_archive.cell(row=1, column=1).value is not None
        
        # Создаем словарь для данных
        data = {}
        
        # Определяем начальную строку для данных
        data_row = last_row if not has_headers else last_row
        
        # Получаем значения из листа Архив
        for excel_col, col_num in column_mapping.items():
            data_key = {
                1: 'match_date',
                2: 'league',
                3: 'home',
                4: 'away',
                5: 'id',
                36: 'prediction',
                36: 'strategy_pred_1',  # AJ - стратегия 1
                37: 'strategy_pred_2', 
                63: 'strategy_pred_3',  # BK - стратегия 2 (нужно проверить точную колонку)
                40: 'home_win_odds',
                41: 'draw_odds',
                42: 'away_win_odds',
                62: 'sport'
            }.get(col_num, f'col_{col_num}')
            
            data[data_key] = get_cell_value(sheet_archive, data_row, col_num)
        
        # Читаем дополнительные коэффициенты из листа коэффициентов
        if SHEET_ODDS in wb.sheetnames:
            sheet_odds = wb[SHEET_ODDS]
            
            data['1x_odds'] = get_cell_value(sheet_odds, 3, 8)  # H3
            data['12_odds'] = get_cell_value(sheet_odds, 3, 9)  # I3
            data['2x_odds'] = get_cell_value(sheet_odds, 3, 10)  # J3
        else:
            print(f"Лист '{SHEET_ODDS}' не найден")
            data['1x_odds'] = ''
            data['12_odds'] = ''
            data['2x_odds'] = ''
        
        wb.close()
        
        print(f"Прочитана строка {data_row} из листа '{SHEET_ARCHIVE}':")
        for key, value in data.items():
            print(f"  {key}: {value}")
        
        return data
        
    except FileNotFoundError:
        print(f"Файл {file_path} не найден")
        return None
    except Exception as e:
        print(f"Ошибка при чтении Excel файла: {e}")
        return None
    
def clear_table(table_name):
    """Очищает все данные из таблицы, но сохраняет структуру"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        # Удаляем все строки из таблицы
        cursor.execute(f'DELETE FROM {table_name}')
        
        # Сбрасываем счетчик автоинкремента (чтобы ID начинались с 1)
        cursor.execute(f'DELETE FROM sqlite_sequence WHERE name = ?', (table_name,))
        
        conn.commit()
        print(f"✅ Таблица '{table_name}' успешно очищена")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при очистке таблицы '{table_name}': {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        print(f"\n{'=' * 60}")
        print(f"РЕЖИМ РАБОТЫ: {'ОТЛАДКА (только вывод)' if DEBUG_MODE else 'РАБОЧИЙ (сохранение в БД)'}")
        print(f"{'=' * 60}\n")
        
        # Определяем путь к Excel файлу (из .env или рядом со скриптом)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        excel_file_path = os.path.join(script_dir, EXCEL_FILENAME)
        
        # Проверяем существование файла
        if not os.path.exists(excel_file_path):
            print(f"Файл не найден по пути: {excel_file_path}")
            excel_file_path = EXCEL_FALLBACK_PATH
            print(f"Пробуем запасной путь: {excel_file_path}")
        
        # Читаем данные из Excel файла
        data = read_excel_file(excel_file_path)
        
        if data is not None:
            # Вставляем данные в базу данных
            success = insert_match_data(data)
            insert_match_data_with_probabilities(data, excel_file_path)

            telegram = TelegramNotifier()
            if success and telegram.is_configured:
                message_text = f"""
📊 Прогноз на матч:
Дата: {data.get('match_date', 'Н/Д')}
Турнир: {data.get('league', 'Н/Д')}
Команды: {data.get('home', 'Н/Д')} - {data.get('away', 'Н/Д')}
Прогноз: {data.get('prediction', 'Н/Д')}
Коэффициенты: 
  • 1: {data.get('home_win_odds', 'Н/Д')}
  • X: {data.get('draw_odds', 'Н/Д')}
  • 2: {data.get('away_win_odds', 'Н/Д')}
"""
                if telegram.send(message_text):
                    print("Данные успешно отправлены в Telegram!")
                    print(f"Отправлено из файла: {excel_file_path}")
            elif success and not telegram.is_configured:
                print("Данные добавлены в БД. Для отправки в Telegram укажите BOT_TOKEN и CHAT_ID в .env")
            else:
                print("Не удалось добавить данные в базу данных")
        else:
            print("Не удалось прочитать данные из Excel файла")

        print("Готово!")
    except Exception as e:
        print(f"Ошибка: {e}")