@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ============================================================
REM  DeluX: коммит кода + push + бэкап БД в Google Drive
REM  Вся логика в backup.py; этот файл — удобная обёртка.
REM ============================================================

set "PY=py -3"
where py >nul 2>&1 || set "PY=python"

echo ========================================
echo   Коммит + Push + Бэкап
echo ========================================
echo.

REM --- Проверка окружения
if not exist "backup.py" (
    echo [!] backup.py не найден. Запустите из папки проекта.
    goto :fail
)

echo Изменённые файлы:
git status --short
echo.

echo Что делать?
echo   1^) Коммит + push + бэкап БД ^(в Google Drive, если настроен^)
echo   2^) Только коммит + push ^(без снимка БД^)
echo   3^) Только бэкап БД ^(без git^)
echo   4^) Проверить состояние Google Drive
echo   0^) Отмена
echo.
set /p "MODE=Выбор [1/2/3/4/0]: "

if "%MODE%"=="0" goto :cancel
if "%MODE%"=="4" (
    %PY% gdrive_backup.py --status
    goto :done
)
if "%MODE%"=="3" goto :db_only
if "%MODE%"=="2" goto :git_only

REM --- 1: полный цикл
echo.
echo Настройки:
echo   тег в git:      да ^(backup-ГГГГММДД-ЧЧММ^)
echo   push в origin:  да
echo   Google Drive:   да ^(если rclone настроен^)
echo.
set /p "MSG=Сообщение коммита (Enter — по умолчанию): "
echo.
if "%MSG%"=="" (
    %PY% backup.py --tag
) else (
    %PY% backup.py --tag -m "%MSG%"
)
if errorlevel 1 goto :fail
goto :done

:git_only
echo.
set /p "MSG=Сообщение коммита (Enter — по умолчанию): "
echo.
if "%MSG%"=="" (
    %PY% backup.py --git-only --tag
) else (
    %PY% backup.py --git-only --tag -m "%MSG%"
)
if errorlevel 1 goto :fail
goto :done

:db_only
echo.
%PY% backup.py --db-only
if errorlevel 1 goto :fail
goto :done

:fail
echo.
echo ========================================
echo   [!] Завершено с ошибками ^(см. выше^)
echo ========================================
echo.
pause
exit /b 1

:cancel
echo Отменено.
goto :done

:done
echo.
echo ========================================
echo   Готово.
echo ========================================
echo.
pause
exit /b 0
