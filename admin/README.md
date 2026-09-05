# DeluX Admin

Nuxt 4 + Vuetify 3 + TypeScript. Read-only просмотр `matches.db` (и теневых parity БД).

## Запуск

```bat
admin.bat
```

или:

```bat
cd admin
npm install
npm run dev
```

Открыть: http://127.0.0.1:3000

Отдельный FastAPI (`api/app.py`) для просмотра не нужен — SQLite читается через Nitro (`node:sqlite`).
