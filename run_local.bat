@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Create a virtual environment and install requirements.txt first.
  echo See README.md for setup instructions.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m app.main
