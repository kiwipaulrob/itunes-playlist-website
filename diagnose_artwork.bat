@echo off
title Diagnose Artwork — HearMyCovers
cd /d "%~dp0"
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found.
    echo Run setup_env.bat first to create it.
    echo.
    pause
    exit /b 1
)

if "%~1"=="" (
    echo Usage:  diagnose_artwork.bat "path\to\Playlist.xml" [track_number]
    echo.
    echo Example:
    echo   diagnose_artwork.bat "C:\Users\prob\OneDrive\Documents2\Playlists\Nuggets 354 - Covers 27 - Isolation.xml"
    echo   diagnose_artwork.bat "...\Nuggets 354 - Covers 27 - Isolation.xml" 3
    echo.
    pause
    exit /b 0
)

echo ========================================
echo  Diagnosing artwork for:
echo  %~1
echo ========================================
echo.
.venv\Scripts\python.exe diagnose_artwork.py %*
echo.
pause
