@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Menyiapkan lingkungan Python pertama kali...
  python -m venv .venv || goto :err
  .venv\Scripts\python -m pip install -r requirements.txt || goto :err
)
.venv\Scripts\python run.py
goto :eof
:err
echo Gagal menyiapkan. Pastikan Python 3.11+ terpasang.
pause
