@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

set "METRICORE_DB_PATH=%CD%\metricore.db"
streamlit run Inicio.py
