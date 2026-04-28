@echo off
rem Quick restart helper for the SEAM dashboard.
rem Run this from the Codex root to pick up logo.py / dashboard.py changes.
cd /d "%~dp0..\..\..\"
echo Launching SEAM dashboard...
python -m seam_runtime.dashboard
