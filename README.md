# MetriCore

Herramienta de gestion metrologica desarrollada con Streamlit y SQLite.

## Versiones preparadas

- Escritorio/local: ver `README_ESCRITORIO.md`.
- Internet/despliegue Streamlit: ver `README_INTERNET.md`.

## Ejecutar rapido en escritorio

```powershell
.\run_desktop.ps1
```

## Modulos principales

- Ficha de equipos.
- Control de mantenimientos.
- Control de calibraciones.
- Condiciones de uso.
- Regla de decision.
- Intervalos de calibracion segun ILAC-G24 / OIML D10.

## Notas tecnicas

La base de datos por defecto es `metricore.db`. Puede cambiarse con:

```text
METRICORE_DB_PATH
```

Para uso en internet con varios usuarios se recomienda migrar la persistencia
a una base de datos administrada.
