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
echo   1^) Полный цикл   ^(list + check + analyze --new, все стратегии 1-9^)
echo   2^) Только список матчей
echo   3^) Анализ новых матчей ^(все стратегии 1-9^)
echo   4^) Проверка результатов ^(БД^)
echo   5^) Проверка calc: стратегии + 10 подстратегий ^(допуск 1%^)
echo   6^) Админка БД ^(Nuxt^)
echo   7^) BTS — обе забьют ^(стратегия #4^)
echo   8^) Favorites — победа фаворита ^(стратегия #5^)
echo   9^) Фавориты — статистика кф ^(backtest^)
echo  10^) StavkaTV — прогнозы stavka.tv ^(стратегия #6^)
echo  11^) Moneyway — dogs/Arbworld ^(стратегия #7^)
echo  12^) 1pr — макс. вероятность «1 пр» ^(стратегия #8^)
echo  13^) WhoScored — точный счёт + фора ^(стратегия #9^)
echo  14^) Загрузить матч по ID
echo  15^) Анализ по выбору ^(все / сезон / матч / сезон заново + стратегия^)
echo  16^) Обнулить рейтинги ^(ELO / Glicko-2 / OpenSkill к исходным^)
echo  17^) Бэкап ^(git-коммит + снимок БД^)
echo   0^) Выход
echo ========================================
set /p "CHOICE=Выбор: "

if "%CHOICE%"=="1" goto :pipeline
if "%CHOICE%"=="2" goto :list
if "%CHOICE%"=="3" goto :analyze
if "%CHOICE%"=="4" goto :check
if "%CHOICE%"=="5" goto :calc_check
if "%CHOICE%"=="6" goto :admin
if "%CHOICE%"=="7" goto :bts
if "%CHOICE%"=="8" goto :favorites
if "%CHOICE%"=="9" goto :favorites_stats
if "%CHOICE%"=="10" goto :stavka_tv
if "%CHOICE%"=="11" goto :dogs
if "%CHOICE%"=="12" goto :onepr
if "%CHOICE%"=="13" goto :whoscored
if "%CHOICE%"=="14" goto :single_match
if "%CHOICE%"=="15" goto :season_url
if "%CHOICE%"=="16" goto :reset_ratings
if "%CHOICE%"=="17" goto :backup
if "%CHOICE%"=="0" exit /b 0
echo Неверный выбор.
goto :menu

:run_args
%PY% delux.py %*
goto :done

:pipeline
echo.
echo [*] Пайплайн: загрузка + проверка результатов + анализ новых...
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

:calc_check
echo.
echo [*] Python-calc: NTB/Betalone/Sniper + 10 подстратегий (допуск 1%%)...
%PY% delux.py calc-check
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

:whoscored
echo.
echo [*] WhoScored — точный счёт + фора (стратегия #9)...
%PY% scripts\run_whoscored_strategy.py --new
goto :done

:single_match
echo.
echo [*] Загрузка матча по ID...
set /p "MATCH_ID=Введите ID матча: "
if "%MATCH_ID%"=="" (
    echo [-] ID матча не введён
    goto :done
)
echo [*] Загрузка матча %MATCH_ID%...
%PY% delux.py analyze --match-id "%MATCH_ID%"
goto :done

:season_url
echo.
echo [*] Анализ по выбору (меню: режим + стратегии)...
%PY% analyze_match.py --interactive
goto :done

:reset_ratings
echo.
echo [*] Обнуление рейтингов: ELO, Glicko-2, OpenSkill.
echo     Рейтинги вернутся к стартовым значениям, история будет очищена.
set /p "CONFIRM=Продолжить? [y/N]: "
if /i not "%CONFIRM%"=="y" (
    echo [-] Отменено
    goto :done
)
%PY% scripts\reset_ratings.py
goto :done

:backup
echo.
echo [*] Бэкап и восстановление.
echo     1^) Сделать бэкап (снимок БД + git-коммит)
echo     2^) Список снимков БД
echo     3^) Восстановить БД из последнего снимка
set /p "BKACT=Действие [1/2/3]: "
if "%BKACT%"=="2" goto :backup_list
if "%BKACT%"=="3" goto :backup_restore
goto :backup_make

:backup_list
%PY% restore.py --list
goto :done

:backup_restore
echo.
echo [!] Текущая БД будет заменена снимком. Закройте админку и анализ.
set /p "BKREST=Продолжить? [y/N]: "
if /i not "%BKREST%"=="y" (
    echo [-] Отменено
    goto :done
)
%PY% restore.py
goto :done

:backup_make
echo.
echo [*] Снимок БД в backups\db\, затем git-коммит кода.
set /p "BKMSG=Сообщение коммита (Enter — по умолчанию): "
if "%BKMSG%"=="" (
    %PY% backup.py --tag
) else (
    %PY% backup.py --tag -m "%BKMSG%"
)
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
