@echo off
setlocal

cd /d "%~dp0..\.."

if not defined SEAM_DB_PATH if exist "%LOCALAPPDATA%\SEAM\state\seam.db" (
  set "SEAM_DB_PATH=%LOCALAPPDATA%\SEAM\state\seam.db"
)

set "EXIT_CODE=0"

if exist ".venv\Scripts\seam-dash.exe" (
  ".venv\Scripts\seam-dash.exe" %*
  set "EXIT_CODE=%ERRORLEVEL%"
) else if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m seam_runtime.dashboard %*
  set "EXIT_CODE=%ERRORLEVEL%"
) else (
  echo Missing repo-local virtual environment.
  echo Create it from the repo root with:
  echo   python -m venv .venv
  echo   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  echo   .\.venv\Scripts\python.exe -m pip install -e ".[dash]"
  set "EXIT_CODE=1"
)

if not "%EXIT_CODE%"=="0" (
  echo.
  echo Dashboard exited with code %EXIT_CODE%.
  pause
)

endlocal & exit /b %EXIT_CODE%
