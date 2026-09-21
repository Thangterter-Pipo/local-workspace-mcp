@echo off
setlocal enabledelayedexpansion

echo =======================================================
echo  Local Workspace MCP - Installation Script (Windows)
echo =======================================================

cd /d "%~dp0\.."

:: Check python availability
set "PY_CMD="
where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=python"
) else (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        set "PY_CMD=py -3"
    )
)

if "%PY_CMD%"=="" (
    echo [ERROR] Khong tim thay Python tren he thong!
    echo Vui long cai dat Python 3.10+ tu https://www.python.org/downloads/
    echo Va nho tich vao option "Add Python to PATH".
    pause
    exit /b 1
)

echo [1/4] Su dung Python he thong:
%PY_CMD% --version

:: Check or create virtual environment
if not exist ".venv" (
    echo [2/4] Dang khoi tao virtual environment (.venv)...
    %PY_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Khoi tao venv that bai!
        pause
        exit /b 1
    )
) else (
    echo [2/4] Da tim thay thu muc .venv san co.
)

:: Upgrade pip inside venv
echo [3/4] Dang nang cap pip trong .venv...
".venv\Scripts\python.exe" -m pip install --upgrade pip

:: Install dependencies
echo [4/4] Dang cai dat cac thu vien tu requirements.txt...
".venv\Scripts\pip.exe" install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Cai dat thu vien that bai!
    pause
    exit /b 1
)

echo.
echo =======================================================
echo  CAI DAT HOAN TAT THANH CONG!
echo  - Chay server truc tiep: run.bat
echo  - Chay ngam supervisor:  start_supervisor.bat
echo =======================================================
