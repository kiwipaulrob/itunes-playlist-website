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

:: Read output_dir from config.ini via build_site.py --print-config
for /f "usebackq delims=" %%D in (`".venv\Scripts\python.exe" "%~dp0build_site.py" --print-config paths.output_dir`) do set OUTPUT_DIR=%%D

if "%OUTPUT_DIR%"=="" (
    echo.
    echo ERROR: Could not read output_dir from config.ini
    echo Make sure config.ini exists alongside build_site.py
    echo.
    pause
    exit /b 1
)

cd /d "%OUTPUT_DIR%"
if errorlevel 1 (
    echo.
    echo ERROR: Could not cd to output directory: %OUTPUT_DIR%
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
echo  https://kiwipaulrob.github.io/hearmycovers/
echo  https://hearmycovers.com
echo ========================================
echo.
pause
