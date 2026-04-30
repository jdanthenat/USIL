@echo off
setlocal enabledelayedexpansion
title USIL — Universal SHA-256 Interoperability Layer

:: ============================================================
::  USIL Simulation Engine — Windows Launcher
::  Order of Operations:
::    1. Check Python is installed
::    2. Install dependencies (rich, requests)
::    3. Run the simulation (Ghost → Shadow → Live + Attacks)
::    4. Start the web dashboard server
::    5. Open browser to dashboard
:: ============================================================

color 0A
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║   USIL — Universal SHA-256 Interoperability Layer   ║
echo  ║   Ghost ^> Shadow ^> Live  ^|  BTC ^> Kaspa  ^|  v2.0    ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: ── STEP 1: Check Python ───────────────────────────────────────────────────
echo  [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python not found.
    echo  Download Python 3.11+ from https://python.org
    echo  Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo         Found: %%v
echo.

:: ── STEP 2: Install dependencies ──────────────────────────────────────────
echo  [2/5] Installing dependencies (rich, requests)...
python -m pip install rich requests --quiet --disable-pip-version-check
if errorlevel 1 (
    echo  WARNING: pip install had issues. Trying to continue anyway...
)
echo         Dependencies ready.
echo.

:: ── STEP 3: Run simulation ────────────────────────────────────────────────
echo  [3/5] Running USIL simulation...
echo         Ghost ^> Shadow ^> Live pipeline
echo         Attack simulator (all 6 threats)
echo         Writing to usil.db (SQLite ledger)
echo.
echo  ┌──────────────────────────────────────────────────────┐
echo  │  SIMULATION OUTPUT                                   │
echo  └──────────────────────────────────────────────────────┘
echo.
python usil_sim.py --fast
if errorlevel 1 (
    echo.
    echo  ERROR: Simulation failed. Check error above.
    pause
    exit /b 1
)
echo.
echo  ✓  Simulation complete. usil.db populated.
echo.

:: ── STEP 4: Start dashboard server ────────────────────────────────────────
echo  [4/5] Starting web dashboard server...
echo         http://localhost:8765
echo.

:: Launch server in new window so terminal stays open
start "USIL Dashboard Server" /min cmd /c "python server.py --no-browser && pause"

:: Give server 1.5 seconds to start
timeout /t 2 /nobreak >nul

:: ── STEP 5: Open browser ──────────────────────────────────────────────────
echo  [5/5] Opening dashboard in browser...
start "" "http://localhost:8765"
echo         Browser opened → http://localhost:8765
echo.

:: ── Done ──────────────────────────────────────────────────────────────────
echo  ╔══════════════════════════════════════════════════════╗
echo  ║   USIL Running                                      ║
echo  ║                                                     ║
echo  ║   Dashboard : http://localhost:8765                 ║
echo  ║   API       : http://localhost:8765/api/live        ║
echo  ║   Ledger    : usil.db  (SQLite)                     ║
echo  ║                                                     ║
echo  ║   To re-run simulation:  python usil_sim.py         ║
echo  ║   Attack sim only:       python usil_sim.py --attacks ║
echo  ║   Stop server:           close the server window   ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: Keep this window open
echo  Press any key to exit this launcher (server keeps running)...
pause >nul
exit /b 0
