@echo off
setlocal

cd /d "%~dp0..\.."

if exist "scripts\windows\launch_dashboard.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\windows\launch_dashboard.ps1" %*
  set "EXIT_CODE=%ERRORLEVEL%"
) else (
  echo Missing dashboard launcher script: scripts\windows\launch_dashboard.ps1
  set "EXIT_CODE=1"
)

if not "%EXIT_CODE%"=="0" (
  echo.
  echo Dashboard exited with code %EXIT_CODE%.
  pause
)

endlocal & exit /b %EXIT_CODE%
