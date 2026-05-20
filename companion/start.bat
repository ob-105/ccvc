@echo off
setlocal
title CC Voice Chat - Companion Server

echo CC Voice Chat - Companion Server
echo =================================
echo.

:: Check Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found.
    echo Install Python 3.8+ from https://python.org and make sure it is on PATH.
    echo.
    pause
    exit /b 1
)

:: Install / upgrade dependencies quietly
echo Installing requirements...
pip install -r requirements.txt --quiet --disable-pip-version-check
if %errorlevel% neq 0 (
    echo ERROR: pip install failed. Check your internet connection or run manually:
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

echo Done.
echo.

:: Optionally launch cloudflared if it is on PATH
where cloudflared >nul 2>&1
if %errorlevel% equ 0 (
    echo Cloudflared found - launching tunnel in a new window...
    start "Cloudflare Tunnel" cmd /k "cloudflared tunnel --url http://localhost:8765"
    echo Copy the wss:// URL from that window into voice_client.lua
    echo.
) else (
    echo Cloudflared not found on PATH.
    echo Download it from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
    echo Then run:  cloudflared tunnel --url http://localhost:8765
    echo.
)

:: Start the server
python server.py

echo.
pause
