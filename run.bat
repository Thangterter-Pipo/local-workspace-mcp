@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [CANH BAO] Chua tim thay moi truong .venv!
    echo Dang tu dong chay scripts\install.bat de thiet lap...
    call scripts\install.bat
    if %errorlevel% neq 0 (
        echo [ERROR] Thiet lap that bai. Khong the chay server.
        pause
        exit /b 1
    )
)

echo Khoi dong Local Workspace MCP (local)...
".venv\Scripts\python.exe" run.py %*
