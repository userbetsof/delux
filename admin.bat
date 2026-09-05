@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0admin"

if not exist "node_modules\nuxt" (
  echo [*] npm install...
  call npm install
)

echo.
echo [*] DeluX Admin: http://127.0.0.1:3000
echo     БД: ..\matches.db  (переключатель в шапке)
echo.
call npm run dev
pause
