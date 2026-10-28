@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DeluX - Google Drive setup

REM ============================================================
REM  Google Drive setup for DB backups (rclone). Run ONCE.
REM  Steps verified against rclone v1.75 on this machine.
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

echo Interactive setup starts next. Answer exactly as listed:
echo.
echo   1. "n/s/q"                    : n      exit new remote
echo   2. name for the new remote    : gdrive   (any name works)
echo   3. storage type               : 24     Google Drive
echo   4. Option client_id           : Enter  use shared one
echo   5. Continue using shared id?  : y
echo   6. Option client_secret       : Enter
echo   7. Option scope               : 1      full access
echo   8. Option service_account_file: Enter
echo   9. Edit advanced config?      : n
echo  10. Use web browser?           : y      browser opens
echo  11. Configure as Shared Drive? : n
echo  12. Keep this remote?          : y
echo  13. "n/s/q"                    : q      quit
echo.
echo NOTE: rclone shared client_id is retired during 2026.
echo       If it fails, create your own client_id in Google Cloud.
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
echo Checking access ^(folder created on first upload^):
rclone lsd gdrive:DeluX 2>nul
if errorlevel 1 echo     Folder DeluX does not exist yet - that is fine.

echo.
echo Done. Backup ^(start.bat item 17^) will now upload to Google Drive.
echo Check: py -3 gdrive_backup.py --status
echo.
pause
exit /b 0
