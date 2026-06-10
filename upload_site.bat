@echo off
title Upload HearMyCovers to GitHub
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found.
    echo Run setup_env.bat first to create it.
    echo.
    pause
    exit /b 1
)

:: Read output_dir from config.ini via helper script
for /f "usebackq delims=" %%D in (`".venv\Scripts\python.exe" _get_output_dir.py`) do set OUTPUT_DIR=%%D

if "%OUTPUT_DIR%"=="" (
    echo.
    echo ERROR: output_dir is missing or blank in config.ini
    echo.
    echo Open config.ini and set output_dir to your site output folder, e.g.:
    echo   output_dir = C:\Users\prob\OneDrive\Documents2\hearmycovers
    echo.
    pause
    exit /b 1
)

if "%OUTPUT_DIR%"=="C:\Users\YOUR_USERNAME\Documents\hearmycovers" (
    echo.
    echo ERROR: config.ini still has the placeholder path for output_dir.
    echo.
    echo Open config.ini and replace:
    echo   C:\Users\YOUR_USERNAME\Documents\hearmycovers
    echo with your actual output folder path.
    echo.
    pause
    exit /b 1
)

cd /d "%OUTPUT_DIR%"
if errorlevel 1 (
    echo.
    echo ERROR: Could not cd to output directory:
    echo   %OUTPUT_DIR%
    echo Check that this folder exists and the path in config.ini is correct.
    echo.
    pause
    exit /b 1
)

echo.

:: One-time git setup if .git folder doesn't exist
if not exist ".git" (
    echo ========================================
    echo  First-time git setup...
    echo ========================================
    echo.
    git init
    git remote add origin https://github.com/kiwipaulrob/hearmycovers.git
    git fetch origin
    git checkout -b main 2>nul
    git branch --set-upstream-to=origin/main main 2>nul
    echo.
    echo  Git repo initialised.
    echo.
)

echo ========================================
echo  Uploading to GitHub Pages...
echo ========================================
echo.
git add .
git commit -m "Update site"
git push --force origin main
echo.
echo ========================================
echo  Done! Site live at:
echo  https://hearmycovers.com
echo ========================================
echo.
pause
