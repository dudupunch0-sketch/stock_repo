@echo off
setlocal

set "SCRIPT_DIR=%~dp0"

where wsl.exe >nul 2>nul
if errorlevel 1 (
  echo wsl.exe was not found.
  echo Run this from WSL instead:
  echo   ./run_stock_agents.sh
  pause
  exit /b 1
)

if "%~1"=="" (
  wsl.exe bash -lc "cd \"$(wslpath '%SCRIPT_DIR%')\" && ./run_stock_agents.sh ask"
) else (
  wsl.exe bash -lc "cd \"$(wslpath '%SCRIPT_DIR%')\" && ./run_stock_agents.sh %*"
)
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
  echo run_stock_agents.sh failed with exit code %EXIT_CODE%.
)
pause
exit /b %EXIT_CODE%
