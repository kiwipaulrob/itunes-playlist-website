@echo off
title Rebuild HearMyCovers Site
cd /d "%~dp0"
echo.
echo ========================================
echo  Rebuilding HearMyCovers site...
echo  (paths and settings read from config.ini)
echo ========================================
echo.
python build_site.py
echo.
echo ========================================
echo  Done! Check output above for errors.
echo ========================================
echo.
pause
