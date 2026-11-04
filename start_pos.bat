@echo off
title SuperMart POS - Launching...
echo ========================================================
echo               SUPERMART POS APPLICATION
echo   Universal Supermarket Billing and Management Platform
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/3] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not found in PATH! Please install Python 3.10+
    pause
    exit /b 1
)

echo [2/3] Initializing Database & Seed Data...
python -c "from app import app, init_database; init_database(app)"
if errorlevel 1 (
    echo [ERROR] Database initialization failed!
    pause
    exit /b 1
)

echo [3/3] Starting Local SuperMart POS Web Server...
echo.
echo ========================================================
echo   Application running at: http://127.0.0.1:5000
echo   Admin Login:   admin   / admin123
echo   Cashier Login: cashier / cashier123
echo ========================================================
echo.
echo Opening browser...
start http://127.0.0.1:5000

python app.py
pause

