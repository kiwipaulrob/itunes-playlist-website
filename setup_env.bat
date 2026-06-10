@echo off
title Setup HearMyCovers Python Environment
cd /d "%~dp0"
echo.
echo ========================================
echo  HearMyCovers — Python environment setup
echo ========================================
echo.

:: Use the py launcher (standard on Windows), fall back to python
where py >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON=py -3
) else (
    where python >nul 2>&1
    if %errorlevel% == 0 (
        set PYTHON=python
    ) else (
        echo ERROR: No Python found. Install Python from python.org or the Microsoft Store.
        pause
        exit /b 1
    )
)

echo Creating virtual environment in .venv ...
%PYTHON% -m venv .venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    pause
    exit /b 1
)
echo.

echo Installing required packages ...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Package installation failed.
    pause
    exit /b 1
)
echo.

echo ========================================
echo  Setup complete!
echo  Run rebuild_site.bat to build the site.
echo ========================================
echo.
pause
