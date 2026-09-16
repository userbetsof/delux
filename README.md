# DeluX IncoProrok

Python-пайплайн ставок: Flashscore → SQLite (`matches.db`) → Python-calc + стратегии #1–8 → Nuxt-админка.

Расчёт **без Excel**: формулы из `data/formulas_cache.json`, константы из `data/constants_cache.json` + `data/lookups.db`. Критерий качества: NTB/Betalone/Sniper совпадают; 10 подстратегий — отклонение ≤ **1%**.

Проверка: `py -3 scripts/compare_strategies.py [match_id]`
(опция `--excel` только если нужен разовый COM-паритет).

## Архитектура

```
delux/
├── delux.py                 # CLI: list / analyze / pipeline / check / стратегии
├── start.bat                # меню Windows
├── src/
│   ├── strategies/          # единый контракт Strategy + реализации #1–8
│   ├── ml/                  # XGBoost, CatBoost, temporal split, MLflow
│   └── pipelines/           # list + analyze
├── formula_port/            # Python-порт формул Excel (calc)
├── favorites_stats/         # backtest фаворитов, травмы
├── admin/                   # Nuxt 4 + Vuetify (чтение matches.db)
├── api/                     # FastAPI (опционально)
├── scripts/                 # служебные/backfill-скрипты
├── archive/                 # VBA, патчи миграции, не runtime
├── data/                    # отчёты JSON (не БД)
└── tests/
```

Корень по-прежнему содержит рабочие модули (`db.py`, `match_analysis.py`, `flashscore_feed.py`, …). Стратегии живут в `src/strategies/`; в корне остались тонкие shim-импорты (`bts_strategy.py` и т.д.), чтобы старые скрипты не ломались.

## Пайплайн

1. **list** — матчи Flashscore в очередь (`match_queue`).
2. **analyze** — данные матча + кф → `formula_port` (NTB/Betalone/Sniper) → стратегии 4–8 → `matches` / `strategy_predictions` / `moneyway`.
3. **check** — результаты Flashscore, расчёт профита по прогнозам.

Запуск полного цикла:

```bash
py -3 -X utf8 delux.py pipeline
```

или `start.bat` → пункт 1.

### Стратегии

| ID | Имя | Откуда сигнал |
|----|-----|----------------|
| 1–3 | NTB / Betalone / Sniper | Python-calc (`formula_port`) |
| 4 | BTS | H2H 2/2 → ОЗ |
| 5 | Favorites | кф фаворита в оптимальном диапазоне |
| 6 | StavkaTV | tipster-прогнозы `stavka_tw/predictions.db` |
| 7 | Moneyway | Arbworld max odds = max volume |
| 8 | 1pr | макс. вероятность подстратегии «1 пр» |

Новая стратегия: класс от `src.strategies.base.Strategy` (`calculate_signals(MatchContext) → StrategySignal | None`) и регистрация в `src.strategies.STRATEGY_CLASSES`.

## Запуск

```bash
copy .env.example .env
py -3 -m pip install -r requirements.txt
py -3 delux.py list
py -3 delux.py analyze --new
py -3 delux.py check --db-only
```

Админка (читает SQLite напрямую):

```bash
cd admin
npm install
npm run dev
```

Открыть http://127.0.0.1:3000 — матчи, прогнозы (свод прибыли), Moneyway, маппинг команд Flashscore → Arbworld.

FastAPI (опционально): `py -3 -m uvicorn api.app:app --host 127.0.0.1 --port 8000`

Тесты: `py -3 -m unittest discover -s tests`

## ML: XGBoost, CatBoost и MLflow

ML-зависимости отделены от рабочего пайплайна:

```bash
py -3 -m pip install -r requirements-ml.txt
py -3 -X utf8 delux.py ml-train
py -3 -X utf8 delux.py ml-predict
py -3 delux.py mlflow-ui
```

MLflow открывается на http://127.0.0.1:5001. Настройки моделей и временного
разбиения находятся в `config/ml/default.json`; артефакты сохраняются в
`artifacts/ml/`, метаданные запусков и прогнозы — в `ml_runs` и
`ml_predictions`.

Обучаются две задачи: исход `1X2` и тотал `ТБ/ТМ 2.5`. Разбиение строго
хронологическое без shuffle. ML-каталог может читать все таблицы SQLite через
read-only соединение, но в признаки намеренно не попадают итоговый счёт,
статус/минута матча, прибыль, фактическая посещаемость, actual-погода и
результаты стратегий. Прогноз стратегий и рассчитанные вероятности разрешаются
только явной настройкой `include_stacking`.

Точечные варианты:

```bash
py -3 delux.py ml-train --model xgboost --target 1x2
py -3 delux.py ml-predict --model catboost --match-id 21qdVdR6
```

## Данные

- Боевая БД: `matches.db` (в git не входит).
- Команды: `teams.name` = Flashscore, `name_arbworld` = Moneyway, `name_whoscored` = WhoScored.
- Пути к Excel/другим проектам — из `.env` (`CALC_WORKBOOK`, `DOGS_ROOT`, `STAVKA_TW_DB`, …).
