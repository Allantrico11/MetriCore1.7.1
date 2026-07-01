# MetriCore - version de escritorio

Esta variante ejecuta la misma app Streamlit en la computadora del laboratorio,
usando SQLite local.

## Requisitos

- Python 3.11 o superior instalado.
- Windows con acceso a PowerShell o CMD.

## Ejecutar

Opcion recomendada:

```powershell
.\run_desktop.ps1
```

Alternativa con doble clic:

```bat
run_desktop.bat
```

El launcher crea un entorno `.venv`, instala dependencias y abre la app en:

```text
http://localhost:8501
```

## Datos

La base se guarda en `metricore.db` dentro de esta carpeta, salvo que se defina
la variable `METRICORE_DB_PATH`.

Esta version es la mas adecuada si el uso sera en una sola computadora o en una
red interna pequena.
