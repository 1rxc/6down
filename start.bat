@echo off
title 6Down - Downloader 606 Web
color 0A
cd /d "%~dp0"

echo ===================================================
echo     Starting 6Down (Downloader 606 Web)...
echo ===================================================
echo.

python run.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred. Press any key to exit.
    pause >nul
)
