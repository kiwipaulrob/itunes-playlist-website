@echo off
title Rebuild HearMyCovers Site
cd /d "%~dp0"
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found.
    echo Run setup_env.bat first to create it.
    echo.
    pause
    exit /b 1
)

echo ========================================
echo  Rebuilding HearMyCovers site...
echo  (paths and settings read from config.ini)
echo ========================================
echo.
.venv\Scripts\python.exe build_site.py
echo.
echo ========================================
echo  Done! Check output above for errors.
echo ========================================
echo.
pause
