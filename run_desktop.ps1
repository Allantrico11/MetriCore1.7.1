$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3 -m venv .venv
}

.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

$env:METRICORE_DB_PATH = Join-Path $PSScriptRoot "metricore.db"
streamlit run Inicio.py
