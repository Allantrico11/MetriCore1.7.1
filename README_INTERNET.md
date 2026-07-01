# MetriCore - version para internet

Esta variante esta lista para desplegar como app Streamlit.

## Archivos clave

- `streamlit_app.py`: entrada comun para plataformas que esperan ese nombre.
- `Inicio.py`: entrada principal real de MetriCore.
- `requirements.txt`: dependencias necesarias.
- `runtime.txt`: version de Python sugerida.
- `.streamlit/config.toml`: tema visual y configuracion de Streamlit.

## Despliegue basico

1. Subir el proyecto a un repositorio Git sin `.venv` ni datos reales.
2. Configurar la plataforma para ejecutar:

```bash
streamlit run streamlit_app.py
```

3. Definir `METRICORE_DB_PATH` si el proveedor ofrece disco persistente.

## Importante sobre SQLite

SQLite sirve para escritorio, demo y uso individual. Para una app en internet
con varios usuarios conviene migrar la persistencia a PostgreSQL, Supabase,
Neon u otra base administrada. Si el hosting no tiene disco persistente,
los cambios guardados en `metricore.db` pueden perderse al reiniciar la app.

## Seguridad

El modulo premium actual usa `st.session_state`, suficiente para prototipo o
demo, pero no para control real de acceso. En internet se recomienda agregar
autenticacion con usuarios, roles y sesiones persistentes.
