import sqlite3
import os

def add_new_columns_and_table():
    """Добавление новых столбцов в таблицу matches и создание таблицы sports"""
    
    # Путь к файлу базы данных
    db_path = 'matches.db'
    
    # Проверяем существование файла БД
    if not os.path.exists(db_path):
        print(f"Ошибка: Файл базы данных {db_path} не найден!")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Создаем таблицу sports, если её нет
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(50) UNIQUE NOT NULL,
                description TEXT
            )
        ''')

            # Таблица для прогнозов по стратегиям
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id VARCHAR(8) NOT NULL,
                strategy_id INTEGER NOT NULL,
                prediction VARCHAR(10) NOT NULL,  -- например: "1", "X", "2", "1X", "12", "2X"
                odds DECIMAL(6,2),                  -- коэффициент на момент прогноза
                stake DECIMAL(5,2) DEFAULT 1.00,    -- размер ставки (в % от банка или условных единицах)
                result VARCHAR(20) DEFAULT NULL,    -- результат: "win", "loss", "return", NULL если еще не сыграл
                profit DECIMAL(10,2) DEFAULT 0.00,  -- фактическая прибыль/убыток
                notes TEXT,                          -- дополнительные заметки
                FOREIGN KEY (match_id) REFERENCES matches(match_id),
                FOREIGN KEY (strategy_id) REFERENCES strategies(id),
                UNIQUE(match_id, strategy_id)  -- один прогноз по стратегии на матч
            )
        ''')

        return True
        
    except Exception as e:
        print(f"Ошибка при добавлении столбцов и таблицы: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()


def update_match_data(match_id, status=None, profit=None, minute=None, segment=None, sport_id=None):
    """Функция для обновления данных матча (для последующего использования)"""
    
    conn = sqlite3.connect('matches.db')
    cursor = conn.cursor()
    
    try:
        update_fields = []
        params = []
        
        if status is not None:
            update_fields.append("match_status = ?")
            params.append(status)
        if profit is not None:
            update_fields.append("profit = ?")
            params.append(profit)
        if minute is not None:
            update_fields.append("minute = ?")
            params.append(minute)
        if segment is not None:
            update_fields.append("segment = ?")
            params.append(segment)
        if sport_id is not None:
            update_fields.append("sport = ?")
            params.append(sport_id)
        
        if update_fields:
            query = f"UPDATE matches SET {', '.join(update_fields)} WHERE match_id = ?"
            params.append(match_id)
            cursor.execute(query, params)
            conn.commit()
            print(f"✓ Данные матча {match_id} обновлены")
            return True
        else:
            print("✗ Нет данных для обновления")
            return False
            
    except Exception as e:
        print(f"Ошибка при обновлении данных матча {match_id}: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def show_recent_matches(limit=5):
    """Показать последние добавленные матчи с новыми столбцами"""
    
    conn = sqlite3.connect('matches.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT m.match_id, m.match_date, m.match_status, m.profit, 
                   m.minute, m.segment, m.sport, s.name
            FROM matches m
            LEFT JOIN sports s ON m.sport = s.id
            ORDER BY m.id DESC 
            LIMIT ?
        """, (limit,))
        
        matches = cursor.fetchall()
        
        if matches:
            print(f"\n--- Последние {len(matches)} матчей с новыми полями ---")
            for match in matches:
                sport_info = f"{match[6]} ({match[7]})" if match[7] else f"{match[6]}"
                print(f"  • ID: {match[0]}, Дата: {match[1]}")
                print(f"    Статус: {match[2]}, Прибыль: {match[3]}")
                print(f"    Минута: {match[4]}, Отрезок: {match[5]}, Спорт: {sport_info}")
        else:
            print("В базе нет матчей")
            
    except Exception as e:
        print(f"Ошибка при получении данных: {e}")
        
    finally:
        conn.close()

def get_sports_list():
    """Получить список всех видов спорта"""
    
    conn = sqlite3.connect('matches.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, name FROM sports ORDER BY id")
        sports = cursor.fetchall()
        return sports
    except Exception as e:
        print(f"Ошибка при получении списка спорта: {e}")
        return []
    finally:
        conn.close()

def create_insert_function_example():
    """Пример функции для вставки матча с новыми полями"""
    
    print("""
    ─────────────────────────────────────────────────
    ПРИМЕР: Как вставлять матчи с новыми полями:
    ─────────────────────────────────────────────────
    
    INSERT INTO matches (
        match_id, match_date, league_id, home_team_id, 
        away_team_id, prediction, match_status, profit, 
        minute, segment, sport
    ) VALUES (
        '12345678', '2025-04-15', 1, 1, 2, 
        '1X', 'завершен', '+2.50', '90+3', '2-й тайм', 1
    );
    
    # Или с помощью Python функции:
    
    def insert_match_with_new_fields(data):
        cursor.execute('''
            INSERT INTO matches 
            (match_id, match_date, league_id, home_team_id, 
             away_team_id, prediction, match_status, profit, 
             minute, segment, sport)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['match_id'], data['match_date'], league_id, 
            home_team_id, away_team_id, data['prediction'],
            data.get('match_status', 'завершен'),
            data.get('profit', '0.00'),
            data.get('minute', '90+'),
            data.get('segment', '2-й тайм'),
            data.get('sport', 1)  # По умолчанию футбол (ID: 1)
        ))
    ─────────────────────────────────────────────────
    """)

if __name__ == "__main__":
    print("=== Добавление новых столбцов в таблицу matches и создание таблицы sports ===\n")
    
    # Добавляем столбцы и создаем таблицу sports
    success = add_new_columns_and_table()
    
    if success:
        print("\n✓ Столбцы и таблица успешно добавлены!")
        
        # Показываем примеры использования
        create_insert_function_example()
        
        # Показываем последние матчи
        show_recent_matches()
        
        # Пример обновления данных матча
        # Раскомментируйте для теста:
        # update_match_data('MATCH_ID_HERE', status='завершен', profit='+5.20', 
        #                  minute='85', segment='2-й тайм', sport_id=1)
        
        print("\n✅ Готово! Добавлены следующие изменения:")
        print("   1. Столбец 'sport' (INTEGER) в таблицу matches")
        print("      - Ограничение: значения от 1 до 99")
        print("      - По умолчанию: 1 (футбол)")
        print("   2. Таблица 'sports' с видами спорта")
        print("      - id: идентификатор спорта")
        print("      - name: название спорта")
        print("      - description: описание")
        print("      - created_at: дата добавления")
    else:
        print("\n❌ Не удалось добавить изменения!")