@echo off
title PoLM Miner — Installation
color 0B
echo.
echo  PoLM Miner — Proof of Legacy Memory
echo  https://polm.com.br
echo  ==========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found!
    echo.
    echo  Please install Python 3.9+ from:
    echo  https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: Check "Add Python to PATH" during install!
    echo.
    pause
    exit /b 1
)

echo  [OK] Python found
echo.

:: Create virtual environment
echo  Installing dependencies...
python -m venv venv
call venv\Scripts\activate.bat

:: Install requirements
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo  [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo  [OK] Dependencies installed
echo.

:: Create start_miner.bat
echo @echo off > start_miner.bat
echo title PoLM Miner >> start_miner.bat
echo call venv\Scripts\activate.bat >> start_miner.bat
echo python polm_miner_gui.py >> start_miner.bat
echo pause >> start_miner.bat

echo  ==========================================
echo  Installation complete!
echo.
echo  To start mining:
echo  - Double-click: start_miner.bat
echo.
echo  Or run now? (press any key to start)
pause >nul

call start_miner.bat
