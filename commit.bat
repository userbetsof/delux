@echo off
REM Git commit script for delux project
REM Commits all changes with a descriptive message

chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo Git Commit Script
echo ========================================
echo.

REM Check git status
echo Checking git status...
git status --short

echo.
echo ========================================
echo Review the changes above.
echo Press any key to continue with commit...
echo ========================================
pause >nul

echo.
echo Adding all changes...
git add -A

echo.
echo Committing...

REM Generate commit message based on changes
set "MSG="

echo.
echo What would you like to commit?
echo.
echo 1. Bug fixes (sport detection, team history, goal probs)
echo 2. Date filter in admin panel
echo 3. Goal probabilities from odds
echo 4. All changes with custom message
echo.
set /p choice="Enter choice (1-4): "

if "%choice%"=="1" (
    set "MSG=fix: sport detection, team history loading, and goal probabilities

- Fix detect_sport_from_html: search match URL path instead of full HTML
  (sidebar contains all sports, causing false positives)
- Fix fetch_match_page_ids: correct array index (ids[0] instead of ids[2])
- Fix team history URL: remove double underscore in suffix (_0_0{suffix})
- Fix recalc_goals_from_odds: lambda limit < 10 -> <= 10
- Load OVER/UNDER odds via Flashscore API for 260 matches
- Fix sport_id for baseball matches (sport=1 -> sport=6)
- Calculate goal_probabilities for all 1669 matches with sport-specific limits"
) else if "%choice%"=="2" (
    set "MSG=feat: add date range filter to admin panel

- Add date picker (range mode) to matches, predictions, and queue pages
- Add date_from/date_to query params to API endpoints
- Format match dates as YYYY.MM.DD HH:MM in UI
- Sort matches by date descending"
) else if "%choice%"=="3" (
    set "MSG=feat: calculate goal probabilities from odds

- Implement recalc_goals_from_odds.py with sport-specific limits:
  football=6, hockey=9, baseball=10
- Load missing odds from Flashscore API for matches without OVER/UNDER
- Normalize database dates to YYYY.MM.DD HH:MM format
- Poisson lambda estimation from OVER/UNDER odds via CDF inversion"
) else if "%choice%"=="4" (
    set /p custom_msg="Enter commit message: "
    set "MSG=%custom_msg%"
) else (
    echo Invalid choice. Using default message.
    set "MSG=fix: various bug fixes and improvements

- Fix sport detection from match page HTML
- Fix team history loading (URL construction, suffix)
- Fix goal probabilities calculation
- Add date filter to admin panel
- Load odds from Flashscore API"
)

git commit -m "%MSG%"

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo Commit successful!
    echo ========================================
    git log -n 1 --oneline
) else (
    echo.
    echo ========================================
    echo Commit failed!
    echo ========================================
)

echo.
pause
