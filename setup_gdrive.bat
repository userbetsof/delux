@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM ============================================================
REM  Настройка Google Drive для бэкапа БД (rclone)
REM  Запускается ОДИН РАЗ. Откроется браузер для входа в Google.
REM ============================================================

echo ========================================
echo   Настройка Google Drive (rclone)
echo ========================================
echo.

where rclone >nul 2>&1
if errorlevel 1 (
    echo [!] rclone не установлен.
    echo     Установите: winget install Rclone.Rclone
    echo     Затем запустите этот файл снова.
    goto :fail
)

echo Текущие настройки:
rclone listremotes
echo.

echo Сейчас запустится интерактивная настройка.
echo Шаги:
echo   1. Вопрос "n/s/q" - введите: n   ^(новый remote^)
echo   2. Имя remote           - введите: gdrive
echo   3. Тип хранилища        - введите номер "Google Drive" ^(обычно 18 или ищите drive^)
echo   4. client_id            - Enter ^(по умолчанию^)
echo   5. client_secret        - Enter ^(по умолчанию^)
echo   6. scope                - введите: 1   ^(полный доступ^)
echo   7. root_folder_id       - Enter
echo   8. service_account_file - Enter
echo   9. Edit advanced config - введите: n
echo  10. Use web browser      - введите: y   ^(откроется браузер^)
echo  11. Войдите в Google и разрешите доступ
echo  12. Configure as Shared Drive - введите: n ^(если не общий диск^)
echo  13. "y/e/d" - введите: y   ^(подтвердить^)
echo  14. Вопрос "n/s/q" - введите: q   ^(выйти^)
echo.
pause

rclone config

echo.
echo ========================================
echo Проверка:
rclone listremotes
echo.

rclone listremotes | findstr /B /I "gdrive:" >nul
if errorlevel 1 (
    echo [!] Remote "gdrive" не создан. Повторите настройку.
    goto :fail
)

echo [+] Remote "gdrive" настроен.
echo.
echo Проверяю доступ к папке:
rclone lsd gdrive:DeluX 2>nul
if errorlevel 1 (
    echo     Папки DeluX пока нет - она создастся при первой загрузке.
)

echo.
echo Готово! Теперь в start.bat пункт 17 бэкап будет уходить в Google Drive.
goto :done

:fail
echo.
pause
exit /b 1

:done
echo.
pause
exit /b 0
