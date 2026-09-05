@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

set "PY=py -3 -X utf8"
set "DELUX_SKIP_ONEPR=1"

echo.
echo [*] Ежедневный паритет Excel vs Python (теневые БД)...
echo.

%PY% scripts\run_daily_parity.py --date today %*

set "ERR=%ERRORLEVEL%"
echo.
if not "%ERR%"=="0" (
    echo [-] Паритет неполный или ошибка. Код: %ERR%
    echo     Смотри data\parity_daily_*.json
) else (
    echo [+] 100%% совпадение Excel и Python за день.
)
pause
exit /b %ERR%
