import sqlite3
import json
import os
import sys
import asyncio
from telegram import Bot
import pandas as pd
import openpyxl

async def send_telegram_message(bot_token, chat_id, message):
    """Асинхронная функция для отправки сообщения в Telegram"""
    bot = Bot(token=bot_token)
    await bot.send_message(chat_id=chat_id, text=message)

def create_database():
    """Создание базы данных и таблиц"""
    conn = sqlite3.connect('matches.db')
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
        description TEXT,
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

def read_excel_file(file_path):
    """Чтение данных из Excel файла и получение последней строки листа 'Архив' и данных из листа 'Коэффициенты'"""
    try:
        # Открываем Excel файл
        df_archive = pd.read_excel(file_path, sheet_name='Архив')
        
        if df_archive.empty:
            print("Лист 'Архив' пуст или не существует")
            return None
        
        # Получаем последнюю строку из листа Архив
        last_row = df_archive.iloc[-1]
        
        # Собираем данные в нужном формате
        column_mapping = {
            'A': 'match_date',
            'B': 'league', 
            'C': 'home',
            'D': 'away',
            'E': 'id',
            'AJ': 'prediction',
            'AN': 'home_win_odds',
            'AO': 'draw_odds',
            'AP': 'away_win_odds',
            'BJ': 'sport',
        }
        
        # Создаем словарь для данных
        data = {}
        
        # Если файл имеет заголовки, используем их
        if df_archive.columns[0] != 0:
            for excel_col, data_key in column_mapping.items():
                try:
                    col_idx = openpyxl.utils.column_index_from_string(excel_col) - 1
                    if col_idx < len(df_archive.columns):
                        col_name = df_archive.columns[col_idx]
                        data[data_key] = str(last_row[col_name]) if pd.notna(last_row[col_name]) else ''
                    else:
                        data[data_key] = ''
                except:
                    data[data_key] = ''
        else:
            for excel_col, data_key in column_mapping.items():
                try:
                    col_idx = openpyxl.utils.column_index_from_string(excel_col) - 1
                    if col_idx < len(df_archive.columns):
                        data[data_key] = str(last_row[col_idx]) if pd.notna(last_row[col_idx]) else ''
                    else:
                        data[data_key] = ''
                except:
                    data[data_key] = ''
        
        # Читаем дополнительные коэффициенты из листа 'Коэффициенты'
        try:
            df_odds = pd.read_excel(file_path, sheet_name='Коэффициенты', header=None)
            
            # Получаем данные из ячеек J3, K3, L3 (индексы: J=9, K=10, L=11, строки: 2 для 0-based)
            if len(df_odds) > 2 and len(df_odds.columns) > 11:
                data['1x_odds'] = str(df_odds.iloc[2, 9]) if pd.notna(df_odds.iloc[2, 9]) else ''
                data['12_odds'] = str(df_odds.iloc[2, 10]) if pd.notna(df_odds.iloc[2, 10]) else ''
                data['2x_odds'] = str(df_odds.iloc[2, 11]) if pd.notna(df_odds.iloc[2, 11]) else ''
            else:
                data['1x_odds'] = ''
                data['12_odds'] = ''
                data['2x_odds'] = ''
                
        except Exception as e:
            print(f"Ошибка при чтении листа 'Коэффициенты': {e}")
            data['1x_odds'] = ''
            data['12_odds'] = ''
            data['2x_odds'] = ''
        
        print(f"Прочитана последняя строка из листа 'Архив':")
        for key, value in data.items():
            print(f"  {key}: {value}")
        
        return data
        
    except FileNotFoundError:
        print(f"Файл {file_path} не найден")
        return None
    except Exception as e:
        print(f"Ошибка при чтении Excel файла: {e}")
        return None
    
if __name__ == "__main__":
    try:
        # Определяем путь к Excel файлу в той же папке, что и скрипт
        script_dir = os.path.dirname(os.path.abspath(__file__))
        excel_file_path = os.path.join(script_dir, "C:\papki\work\Bets\DeluX_IncoProrok_fix_05-2025.xlsm")
        
        # Читаем данные из Excel файла
        data = read_excel_file(excel_file_path)
        
        if data is not None:
            # Вставляем данные в базу данных
            success = insert_match_data(data)
            
            if success:
                BOT_TOKEN = "6055776005:AAGPEEGBcTlKNgKkee1CEUmdAyhBiCvnciw"
                CHAT_ID = "736114046"
                
                # Форматируем сообщение для лучшей читаемости
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
                
                # Отправляем сообщение в Telegram
                asyncio.run(send_telegram_message(BOT_TOKEN, CHAT_ID, message_text))
                
                print("Данные успешно отправлены в Telegram!")
                print(f"Отправлено из файла: {excel_file_path}")
            else:
                print("Не удалось добавить данные в базу данных")
        else:
            print("Не удалось прочитать данные из Excel файла")

        print("Готово!")
    except Exception as e:
        print(f"Ошибка: {e}")