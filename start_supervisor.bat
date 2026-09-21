@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [CANH BAO] Chua tim thay .venv! Vui long chay scripts\install.bat truoc.
    pause
    exit /b 1
)

echo Dang khoi dong Local Workspace MCP Supervisor chay ngam...
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" start_mcp.py %*
) else (
    start /B "" ".venv\Scripts\python.exe" start_mcp.py %*
)

echo Supervisor da duoc khoi dong ngam.
echo - Kiem tra trang thai: .venv\Scripts\python.exe start_mcp.py status
echo - Dung supervisor:     .venv\Scripts\python.exe start_mcp.py stop
echo - Thu muc log tai:     %%LOCALAPPDATA%%\LocalWorkspaceMCP
