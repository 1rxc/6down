@echo off
setlocal
title 6Down - Free Family & Friends Link

echo =======================================================
echo     6Down - Share Online for Free (Zero Cost)
echo =======================================================
echo.

:: Check if server is running
curl -s http://localhost:6060/api/health >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Starting 6Down server in background...
    start /b python run.py >nul 2>&1
    timeout /t 2 /nobreak >nul
)

:: Check if cloudflared exists
if not exist "cloudflared.exe" (
    echo [*] Downloading free Cloudflare Tunnel tool...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile 'cloudflared.exe'"
)

echo.
echo =======================================================
echo [*] Generating secure free HTTPS link for your family...
echo [*] Send the link below to your family and friends!
echo =======================================================
echo.

cloudflared.exe tunnel --url http://localhost:6060
pause
