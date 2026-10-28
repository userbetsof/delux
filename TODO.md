# TODO — Дорожная карта проекта DeluX

## 🔴 Приоритет: Высокий

### 1. XGBoost: минимизация фичей до 80 ключевых параметров
**Статус:** ⬜ Pending  
**Файлы:** `src/ml/features.py`, `src/ml/train.py`, `src/strategies/xgboost.py`

**Проблема:**  
XGBoost сейчас использует ~80+ признаков, но многие из них шумовые или дублирующие. Модель путается и теряет точность.

**Задачи:**
- [ ] Провести feature importance analysis (XGBoost feature importance + SHAP values)
- [ ] Отфильтровать признаки по корреляции (удалить дублирующие с r > 0.9)
- [ ] Оставить топ-80 признаков по importance score
- [ ] Провести grid search по количеству фичей (50, 80, 100, 150)
- [ ] Бэктест на сокращённом наборе фичей
- [ ] Обновить `build_feature_dataset()` в `src/ml/features.py`

**Ожидаемый результат:**  
Модель с 80 фичами, которая лучше обобщает и не переобучается.

---

### 2. Архивация матчей за 10 лет по избранным лигам и всем видам спорта
**Статус:** ✅ Выполнено (базовый парсинг)  
**Файлы:** `test_flashscore.py`

**Реализовано:**
- ✅ Тестовая БД `test_flashscore.db` с 14 матчами АПЛ 2016
- ✅ Парсинг `tr_` feed (матчи тура) — 5 страниц
- ✅ Парсинг `to_` feed (таблица лиги) — 20 команд
- ✅ URL паттерн: `tr_{sport}_{tournament_id}_{page}_{lang}`
- ✅ Разделитель матчей: `AA÷` (не MIT÷)

**Результаты парсинга:**
```
Page 0: 107 matches
Page 1: 100 matches
Page 2: 100 matches
Page 3: 80 matches
Total: 387 matches
```

**Примеры матчей:**
```
Chelsea vs Arsenal 3-1
Sunderland vs Man Utd 4-0
Everton vs Stoke 1-1
Swansea vs Man City 5-1
```

---

### 3. Загрузка архива: избранные лиги + все виды спорта за 10 лет
**Статус:** ⬜ Pending  
**Файлы:** `archive_matches.py`, `delux.py`, `.env`

**Задачи:**
- [ ] Добавить в `.env`: `DELUX_FAVORITE_LEAGUES` (список лиг через запятую)
- [ ] Добавить в `.env`: `DELUX_ARCHIVE_SPORTS` (список видов спорта)
- [ ] Реализовать `archive_leagues()` в `archive_matches.py`
- [ ] Оптимизация: сначала проверить, есть ли матчи в БД, пропускать если есть
- [ ] Логирование прогресса (сколько матчей загружено, ошибок)
- [ ] Обработка ошибок и retry для failed запросов

**Ожидаемый результат:**  
Автоматическая загрузка архива по конфигурации из `.env`.

---

## 🟡 Пр��оритет: Средний

### 4. Добавить рейтинги Glicko-2 и/или OpenSkill
**Статус:** ✅ Выполнено  
**Файлы:** `ratings.py`, `db.py`

**Реализовано:**
- ✅ Модуль `ratings.py` с Glicko-2 рейтингами
- ✅ Таблицы `glicko2_ratings` и `glicko2_rating_history`
- ✅ Формула Glicko-2 с expected score и home advantage (+100)
- ✅ Обновление rating, RD, volatility после каждого матча
- ✅ CLI команды: `update`, `recalculate`, `list`
- ✅ Полная миграция БД

**Результаты:**
```
[GLICKO2] Recalculated: 341 teams, 1764 matches
  Duration: 95.2ms

Top 5 teams (sport=1):
1. Бостон Ред Сокс     1595.94 (RD: 189)
2. Самсунг Лайонс      1584.04 (RD: 162)
3. Интер               1583.85 (RD: 220)
4. Манчестер Юнайтед   1583.78 (RD: 220)
5. Милуоки Брюэрс      1571.92 (RD: 139)
```

**CLI команды:**
```bash
# Пересчитать все рейтинги
python delux.py ratings recalculate [--sport 1]

# Обновить для конкретного матча
python delux.py ratings update --match-id <id>

# Список рейтингов
python delux.py ratings list [--sport 1]
```

**Задачи на будущее:**
- [ ] OpenSkill (поддержка 1-X-1 форматов)
- [ ] Интеграция Glicko-2 как фичи в XGBoost
- [ ] Бэктест: ELO vs Glicko-2
- [ ] API endpoints для admin UI

---

### 5. Парсинг истории движения кф с Oddsportal.com
**Статус:** ⬜ Pending  
**Файлы:** `src/odds_portal.py` (NEW), `db.py`

**Проблема:**  
В БД хранятся только текущие коэффициенты (`odds` table). Нет истории изменения кф — нельзя анализировать:
- Движение линии (line movement)
- Пик активности (volume spike)
- Расхождения между БК (value betting)
- Реакцию рынка на новости

**Задачи:**
- [ ] Создать `src/odds_portal.py`
  - [ ] Парсинг Oddsportal.com через BeautifulSoup/Playwright
  - [ ] URL паттерн: `https://www.oddsportal.com/match/{match_id}/odds/`
  - [ ] Извлечение истории кф по БК (Pinnacle, Bet365, William Hill и др.)
  - [ ] Сохранение в БД: `odds_history` (match_id, bookmaker, market, odds, timestamp)
- [ ] Поля для сохранения:
  - [ ] `match_id` — идентификатор матча
  - [ ] `bookmaker` — название БК
  - [ ] `market` — 1X2, Over/Under, BTTS
  - [ ] `outcome` — П1, X, П2, Over 2.5, Under 2.5
  - [ ] `odds_value` — коэффициент
  - [ ] `odds_timestamp` — время фиксации
  - [ ] `odds_source` — scraped/predicted
- [ ] Функции:
  - [ ] `fetch_odds_history(match_id)` — загрузка истории для одного матча
  - [ ] `fetch_odds_history_batch(match_ids)` — пакетная загрузка
  - [ ] `get_line_movement(match_id)` — анализ движения линии
  - [ ] `detect_value_opportunities()` — поиск расхождений между БК
- [ ] Оптимизация:
  - [ ] Кэширование ответов (Redis/file cache)
  - [ ] Rate limiting (не более 1 req/sec)
  - [ ] Retry с exponential backoff
  - [ ] Обработка капчи (Cloudflare)
- [ ] CLI:
  - [ ] `python delux.py odds-portal fetch --match-id <id>`
  - [ ] `python delux.py odds-portal fetch --date 2024.01.15`
  - [ ] `python delux.py odds-portal analyze --match-id <id>`

**Ожидаемый результат:**  
История движения коэффициентов для всех матчей, позволяющая:
- Анализировать line movement (ранние vs поздние кф)
- Находить value betting возможности (расхождения между БК)
- Отслеживать реакцию рынка на новости/травмы
- Использовать как фичи для ML моделей (momentum, volatility)

---

### 6. Отображение статистики матчей из формы (form stats)
**Статус:** ⬜ Pending  
**Файлы:** `admin/app/pages/` (Nuxt), `admin/app/components/`

**Задачи:**
- [ ] Создать компонент `MatchFormStats.vue`
  - [ ] Отображение последних 5-10 матчей каждой команды
  - [ ] Визуализация формы (W/D/L цвета)
  - [ ] Статистика: голы забитые/пропущенные средние
  - [ ] Тренды (последние 3 матча: improves/stagnant/worsens)
- [ ] Добавить API endpoint в `server/api/` для form stats
- [ ] Интеграция в страницу матча (`admin/app/pages/matches/[id].vue`)
- [ ] Добавить фильтры: по виду спорта, лиге, периоду

**Ожидаемый результат:**  
В UI можно видеть форму команд перед матчем и статистику за последние N игр.

---

### 7. Оптимизация существующих стратегий
**Статус:** ⬜ Pending  
**Файлы:** `scripts/run_*_strategy.py`, `backtest_*.py`

**Стратегии для оптимизации:**
- [ ] **BTS (#4)** — обе забьют: оптимизировать пороги для разных лиг
- [ ] **Favorites (#5)** — победа фаворита: найти оптимальный диапазон кф
- [ ] **StavkaTV (#6)** — прогнозы tipster'ов: взвешенный рейтинг прогнозеров
- [ ] **Moneyway (#7)** — Arbworld volume-based: оптимизировать volume threshold
- [ ] **1pr (#8)** — макс вероятность: отбор по лигам/видам спорта
- [ ] **WhoScored (#9)** — точный счёт + фора: фильтры по confidence

**Метрики для каждой стратегии:**
- ROI, Win Rate, Profit per bet
- Разбивка по видам спорта, лигам, периодам
- Корреляция с XGBoost предсказаниями

**Ожидаемый результат:**  
Отфильтрованные стратегии с ROI > 0, оптимизированные пороги.

---

## 🟢 Приоритет: Низкий

### 7. Поиск и анализ новых стратегий
**Статус:** ⬜ Pending  
**Файлы:** `scripts/` (NEW), `backtest_new.py`

**Идеи для новых стратегий:**
- [ ] **Over/Under 2.5** — на основе средних голов команд (history + H2H)
- [ ] **Handicap** — фора на основе разницы рейтингов (ELO/Glicko)
- [ ] **Double Chance** — 1X или X2 при большой разнице классов
- [ ] **BTTS + Over** — комбинированная стратегия
- [ ] **Live betting** — стратегии для ставок в матче (на основе minute + score)
- [ ] **ML-ensemble** — голосование XGBoost + CatBoost + ELO
- [ ] **Value betting** — поиск завышенных коэффициентов (model prob > implied prob)

**Методология:**
- [ ] Генерация сигналов на исторических данных
- [ ] Бэктест с учётом комиссий и дисперсии
- [ ] Анализ по видам спорта и лигам
- [ ] Оптимизация порогов (grid search)

**Ожидаемый результат:**  
5+ новых стратегий с подтверждённым ROI > 0.

---

### 8. Кастомный XG рейтинг (ожидаемые годы)
**Статус:** ⬜ Pending  
**Файлы:** `src/ratings/xg_rating.py` (NEW)

**Идея:**  
Создать собственный рейтинг на основе XG (Expected Goals) с прогнозом ожидаемых лет/сезонов на вершине таблицы.

**Задачи:**
- [ ] Создать `src/ratings/xg_rating.py`
  - [ ] XG (Expected Goals) на основе xG матча + форма команд
  - [ ] Rating = функция от xG difference + форма + H2H
  - [ ] Прогноз: сколько лет/сезонов команда продержится в текущем дивизионе
  - [ ] Прогноз: когда команда выйдет/вылетит
- [ ] Фичи рейтинга:
  - [ ] xG за матч (из match_stats)
  - [ ] xG difference за последние 10 матчей
  - [ ] Форма (последние 5 матчей: W/D/L)
  - [ ] H2H dominance ratio
  - [ ] Rating ELO/Glicko-2 как базовая линия
  - [ ] Home advantage factor (per league)
- [ ] Прогноз «ожидаемые годы»:
  - [ ] Скорость набора очков (points per game)
  - [ ] Оставшиеся матчи в сезоне
  - [ ] Сложность оставшихся opponents
  - [ ] Вероятность выхода/вылета по сезонам
- [ ] Интеграция:
  - [ ] Сохранение в БД: `xg_ratings`, `xg_projections`
  - [ ] CLI: `python delux.py xg-rating recalculate`
  - [ ] API для admin UI

**Ожидаемый результат:**  
Рейтинг, который не только ранжирует команды, но и прогнозирует:
- Сколько лет команда продержится в текущем дивизионе
- Вероятность выхода в элиту / вылета
- Динамику рейтинга по сезонам

---

### 9. Расчёт расстояний между стадионами
**Статус:** 🟡 In Progress  
**Файлы:** `db.py`, `venues.py`, `src/ml/features.py`

**Реализовано:**
- ✅ Haversine формула в `db.py`
- ✅ Таблицы `venues` и `venue_distances`
- ✅ CLI `python delux.py venues geocode` — геокодирование стадионов (Nominatim API)
- ✅ CLI `python delux.py venues distances` — массовый расчёт расстояний
- ✅ CLI `python delux.py venues analysis` — анализ влияния на результаты
- ✅ CLI `python delux.py venues all` — полный пайплайн
- ✅ CLI `python delux.py venues feature` — добавить distance в XGBoost
- ✅ Distance как фича `distance_km` в `src/ml/features.py`

**Базовые координаты:**
- Встроены координаты 30+ городов (Россия, Европа, Америка)
- Geocoding через Nominatim (OpenStreetMap) — бесплатный, без ключа

**Задачи:**
- [ ] Запустить `python delux.py venues geocode` для заполнения координат
- [ ] Запустить `python delux.py venues distances` для расчёта
- [ ] Запустить `python delux.py venues analysis` для проверки
- [ ] Запустить `python delux.py venues feature` для добавления в XGBoost

**Ожидаемый результат:**  
Distance между стадионами как одна из фичей модели.

---

## Сводная таблица

| # | Задача | Приоритет | Статус | Файлы |
|---|--------|-----------|--------|-------|
| 1 | XGBoost: 80 фичей | 🔴 Высокий | ⬜ | `src/ml/features.py` |
| 2 | Архивация 10 лет | 🟡 Средний | ✅ | `test_flashscore.py` |
| 3 | Загрузка избранных лиг | 🔴 Высокий | ⬜ | `archive_matches.py` |
| 4 | Glicko-2 / OpenSkill | 🟡 Средний | ✅ | `ratings.py` |
| 5 | Oddsportal.com кф | 🟡 Средний | ⬜ | `src/odds_portal.py` |
| 6 | Form stats в UI | 🟡 Средний | ⬜ | `admin/app/pages/` |
| 7 | Оптимизация стратегий | 🟡 Средний | ⬜ | `scripts/run_*` |
| 8 | Новые стратегии | 🟢 Низкий | ⬜ | `scripts/` |
| 9 | Кастомный XG рейтинг | 🟢 Низкий | ⬜ | `src/ratings/xg_rating.py` |
| 9 | Расстояния стадионов | 🟢 Низкий | 🟡 | `db.py` |
