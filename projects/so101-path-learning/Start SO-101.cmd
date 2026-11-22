@echo off
setlocal
cd /d "%~dp0"
set OPENBLAS_NUM_THREADS=1
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -c "import mujoco,numpy,scipy;assert mujoco.__version__=='3.3.7'" >nul 2>&1
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -c "import urllib.request,json; assert 'report' in json.load(urllib.request.urlopen('http://127.0.0.1:8766/api/info',timeout=.5))" >nul 2>&1
if not errorlevel 1 (
  start "" "http://127.0.0.1:8766/"
  exit /b 0
)
".venv\Scripts\python.exe" studio.py --open
if errorlevel 1 goto failed
exit /b 0
:failed
echo The SO-101 simulator could not start. See the message above.
pause
exit /b 1
