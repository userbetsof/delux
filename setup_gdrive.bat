@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DeluX - Google Drive setup

REM ============================================================
REM  Google Drive setup for DB backups (rclone). Run ONCE.
REM ============================================================

echo ========================================
echo   Google Drive setup (rclone)
echo ========================================
echo.

where rclone >nul 2>&1
if errorlevel 1 (
    echo [!] rclone is not installed.
    echo     Install: winget install Rclone.Rclone
    echo     Then run this file again.
    echo.
    pause
    exit /b 1
)

echo Current remotes:
rclone listremotes
echo.

echo Interactive setup will start now.
echo.
echo   1. "n/s/q"              - type: n
echo   2. name for remote      - type: gdrive
echo   3. storage type         - choose Google Drive
echo   4. client_id            - Enter
echo   5. client_secret        - Enter
echo   6. scope                - type: 1   (full access)
echo   7. root_folder_id       - Enter
echo   8. service_account_file - Enter
echo   9. Edit advanced config - type: n
echo  10. Use web browser      - type: y   (browser will open)
echo  11. Sign in to Google and allow access
echo  12. Shared Drive         - type: n
echo  13. "y/e/d"              - type: y
echo  14. "n/s/q"              - type: q
echo.
pause

rclone config

echo.
echo ========================================
echo Check:
rclone listremotes
echo.

rclone listremotes | findstr /B /I "gdrive:" >nul
if errorlevel 1 (
    echo [!] Remote "gdrive" was not created. Please run setup again.
    echo.
    pause
    exit /b 1
)

echo [+] Remote "gdrive" is configured.
echo.
echo Checking access to folder:
rclone lsd gdrive:DeluX 2>nul
if errorlevel 1 echo     Folder DeluX does not exist yet - it will be created on first upload.

echo.
echo Done. Backup in start.bat item 17 will now upload to Google Drive.
echo.
pause
exit /b 0
