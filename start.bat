@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

rem DeluX — Python пайплайн (CALC_BACKEND=python из .env)
set "PY=py -3 -X utf8"

if not "%~1"=="" goto :run_args

:menu
echo.
echo ========================================
echo   DeluX IncoProrok (Python)
echo ========================================
echo   1^) Полный цикл   ^(list + analyze --new, все стратегии 1-8^)
echo   2^) Только список матчей
echo   3^) Анализ новых матчей ^(все стратегии 1-8^)
echo   4^) Проверка результатов ^(БД^)
echo   5^) Открыть Excel ^(xlsm^)
echo   6^) Паритет Excel vs Python ^(день^)
echo   7^) Админка БД ^(Nuxt^)
echo   8^) BTS — обе забьют ^(стратегия #4^)
echo   9^) Favorites — победа фаворита ^(стратегия #5^)
echo  10^) Фавориты — статистика кф ^(backtest^)
echo  11^) StavkaTV — прогнозы stavka.tv ^(стратегия #6^)
echo  12^) Moneyway — dogs/Arbworld ^(стратегия #7^)
echo  13^) 1pr — макс. вероятность «1 пр» ^(стратегия #8^)
echo   0^) Выход
echo ========================================
set /p "CHOICE=Выбор: "

if "%CHOICE%"=="1" goto :pipeline
if "%CHOICE%"=="2" goto :list
if "%CHOICE%"=="3" goto :analyze
if "%CHOICE%"=="4" goto :check
if "%CHOICE%"=="5" goto :excel
if "%CHOICE%"=="6" goto :parity
if "%CHOICE%"=="7" goto :admin
if "%CHOICE%"=="8" goto :bts
if "%CHOICE%"=="9" goto :favorites
if "%CHOICE%"=="10" goto :favorites_stats
if "%CHOICE%"=="11" goto :stavka_tv
if "%CHOICE%"=="12" goto :dogs
if "%CHOICE%"=="13" goto :onepr
if "%CHOICE%"=="0" exit /b 0
echo Неверный выбор.
goto :menu

:run_args
%PY% delux.py %*
goto :done

:pipeline
echo.
echo [*] Пайплайн: загрузка + анализ новых...
%PY% delux.py pipeline
goto :done

:list
echo.
echo [*] Загрузка списка матчей в БД...
%PY% delux.py list
goto :done

:analyze
echo.
echo [*] Анализ новых матчей...
%PY% delux.py analyze --new
goto :done

:check
echo.
echo [*] Проверка результатов в БД...
%PY% delux.py check --db-only
goto :done

:excel
set "XLSM="
if exist "delux_incoprorok_mvp.xlsm" set "XLSM=delux_incoprorok_mvp.xlsm"
if exist "DeluX_IncoProrok_mvp.xlsm" set "XLSM=DeluX_IncoProrok_mvp.xlsm"
if exist "DeluX_IncoProrok_mvp0.xlsm" if "%XLSM%"=="" set "XLSM=DeluX_IncoProrok_mvp0.xlsm"
if "%XLSM%"=="" (
    echo [-] xlsm не найден в %cd%
    goto :done
)
echo [*] Открытие %XLSM% ...
start "" "%XLSM%"
goto :eof

:parity
echo.
echo [*] Паритет Excel vs Python за сегодня...
set "DELUX_SKIP_ONEPR=1"
%PY% scripts\run_daily_parity.py --date today
goto :done

:admin
echo.
echo [*] Запуск админки: http://127.0.0.1:3000
cd /d "%~dp0admin"
if not exist "node_modules\nuxt" call npm install
call npm run dev
goto :done

:bts
echo.
echo [*] BTS — стратегия «обе забьют» (очные 2/2)...
%PY% scripts\run_bts_strategy.py --new
goto :done

:favorites
echo.
echo [*] Favorites — победа фаворита (стратегия #5)...
%PY% scripts\run_favorites_strategy.py --new
goto :done

:favorites_stats
echo.
echo [*] Статистика ставок на фаворитов...
%PY% scripts\run_favorites_stats.py
goto :done

:stavka_tv
echo.
echo [*] StavkaTV — прогнозы tipster'ов (стратегия #6)...
%PY% scripts\run_stavka_tv_strategy.py --new
goto :done

:dogs
echo.
echo [*] Moneyway — Arbworld dogs (стратегия #7)...
%PY% scripts\run_dogs_strategy.py --new
goto :done

:onepr
echo.
echo [*] 1pr — макс. вероятность «1 пр» (стратегия #8)...
%PY% scripts\run_onepr_strategy.py --new
goto :done

:done
set "ERR=%ERRORLEVEL%"
echo.
if not "%ERR%"=="0" (
    echo [-] Ошибка, код %ERR%
) else (
    echo [+] Готово.
)
pause
exit /b %ERR%
