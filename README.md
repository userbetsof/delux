# delux

## Admin UI (Nuxt) + API (FastAPI)

### FastAPI (просмотр БД `matches.db`)

- **Файл**: `c:\papki\work\bets\delux\api\app.py`
- **Переменные окружения** (в `.env`):
  - `DATABASE_PATH` (по умолчанию `matches.db`)
  - `ADMIN_CORS_ORIGINS` (по умолчанию `*`)

Запуск (Windows PowerShell):

```bash
py -3 -m pip install -r requirements.txt
py -3 -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Проверка: `GET http://127.0.0.1:8000/health`

### Nuxt 4 + Vuetify 3 admin

- **Папка**: `c:\papki\work\bets\delux\admin`
- **Переменная**: `NUXT_PUBLIC_API_BASE` (по умолчанию `http://127.0.0.1:8000`)
- **Стек**: Nuxt `4.4.2`, Vuetify `3.12.3`

Запуск:

```bash
cd admin
npm install
set NUXT_PUBLIC_API_BASE=http://127.0.0.1:8000
npm run dev
```

Открыть в браузере адрес, который покажет Nuxt (обычно `http://localhost:3000`).

### Доступные API эндпоинты

- `GET /matches?status=&limit=&offset=`
- `GET /matches/{match_id}`
- `GET /matches/{match_id}/odds`
- `GET /matches/{match_id}/goal-probabilities`
- `GET /matches/{match_id}/outcome-probabilities`
- `GET /countries`
- `GET /leagues?country_id=`
- `GET /teams`
- `GET /odds?limit=&offset=`