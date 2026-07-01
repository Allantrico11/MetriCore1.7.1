"""
=============================================================================
Plataforma de Evaluación de Conformidad Metrológica - Regla de Decisión
Basada en ISO/IEC 17025:2017, ILAC G8:2009, ISO 14253-1:2017
=============================================================================

Aplicación Streamlit de un único módulo. El usuario:
  1. Configura el instrumento/ítem, los límites de especificación y la
     regla de decisión a aplicar.
  2. Ingresa los datos de medición (manualmente o desde el catálogo de
     equipos / CSV).
  3. Obtiene la declaración de conformidad, el análisis de riesgos (PFA/PFR)
     y el gráfico de zonas de conformidad.
  4. Descarga un informe profesional en Word, listo para el cliente.
"""

import io
import json
import os
import sys
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from utils import (
    aplicar_estilos,
    mostrar_errores_validacion,
    validar_numero,
    validar_texto,
    validar_unidad,
)
from database import get_equipos
from regla_decision.logica_rd import (
    INF, REGLAS, evaluar_punto, calcular_AL,
    probabilidad_mas_alla, probabilidad_mas_alla_inferior,
)
from regla_decision.graficos_rd import grafico_individual, grafico_comparativo
from regla_decision.informe_docx import generar_informe_docx

# =============================================================================
# CONFIGURACIÓN DE PÁGINA
# =============================================================================

st.set_page_config(
    page_title="Regla de Decisión — MetriCore",
    page_icon="📐",
    layout="wide",
)
aplicar_estilos()

if "premium_activo" not in st.session_state or not st.session_state.premium_activo:
    with st.container(border=True):
        st.warning("🔒 Este módulo requiere el Plan Premium.")
        st.caption("Ve a **Acceso a Plan Premium** en el menú lateral para activarlo.")
    st.stop()

DATA_DIR = os.path.join(ROOT_DIR, "regla_decision")
CATALOGO_PATH  = os.path.join(DATA_DIR, "catalogo_equipos.json")
HISTORIAL_PATH = os.path.join(DATA_DIR, "historial_analisis.json")

COLOR_VERDE = "#15924a"
COLOR_AMARILLO = "#b8860b"
COLOR_ROJO = "#c0392b"


def _ss_float(key: str, fallback: float) -> float:
    """
    Recupera un valor numérico guardado en session_state, usando el valor
    de respaldo (`fallback`) si la clave no existe, si su valor es None, o
    si no es un número finito.

    Esto evita el error `TypeError: float() argument must be a string or a
    real number, not 'NoneType'`: algunos campos (p. ej. la tolerancia en
    modo "Solo Máximo/Mínimo", o el multiplicador en la regla "Aceptación
    Simple") se guardan como None porque en ese modo no aplican. Si luego
    el usuario vuelve a un modo donde sí se usan, `st.session_state.get`
    encuentra la clave (con valor None) y por lo tanto NO usa el valor por
    defecto, lo que rompía `float(None)`.
    """
    val = st.session_state.get(key)
    try:
        val = float(val)
    except (TypeError, ValueError):
        return float(fallback)
    if val != val or abs(val) >= 1e15:   # NaN o "infinito" interno (±INF)
        return float(fallback)
    return val


# =============================================================================
# CATÁLOGO DE EQUIPOS (persistencia simple en JSON local)
# =============================================================================

def cargar_catalogo() -> list[dict]:
    if os.path.exists(CATALOGO_PATH):
        try:
            with open(CATALOGO_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def guardar_catalogo(catalogo: list[dict]):
    with open(CATALOGO_PATH, "w", encoding="utf-8") as f:
        json.dump(catalogo, f, ensure_ascii=False, indent=2)


# =============================================================================
# HISTORIAL (persistencia en JSON local, sin bytes de informe)
# =============================================================================

def cargar_historial() -> list[dict]:
    if os.path.exists(HISTORIAL_PATH):
        try:
            with open(HISTORIAL_PATH, "r", encoding="utf-8") as f:
                registros = json.load(f)
            # Decodificar bytes de informe desde base64
            import base64
            for r in registros:
                b64 = r.get("informe_b64")
                if b64:
                    try:
                        r["informe_bytes"] = base64.b64decode(b64)
                    except Exception:
                        r["informe_bytes"] = None
                else:
                    r["informe_bytes"] = None
                r.pop("informe_b64", None)
            return registros
        except Exception:
            return []
    return []


def guardar_historial(historial: list[dict]):
    """Guarda el historial en JSON. Los bytes del informe se codifican en base64."""
    import base64
    try:
        registros = []
        for e in historial:
            r = {k: v for k, v in e.items() if k != "informe_bytes" and k != "informe_b64"}
            ib = e.get("informe_bytes")
            if isinstance(ib, (bytes, bytearray)) and len(ib) > 0:
                r["informe_b64"] = base64.b64encode(ib).decode("ascii")
            else:
                r["informe_b64"] = None
            registros.append(r)
        with open(HISTORIAL_PATH, "w", encoding="utf-8") as f:
            json.dump(registros, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# =============================================================================
# ESTADO DE SESIÓN
# =============================================================================

defaults = {
    "historial": [],
    "mediciones": [{"etiqueta": "Punto 1", "valor_medido": 0.0, "incertidumbre": 0.05}],
    "catalogo": None,
    "config": {},
    "df_resultados": None,
    # Valores persistentes de configuración
    "cfg_nombre": "Ítem #1",
    "cfg_unidad": "mm",
    "cfg_nominal": 0.0,
    "cfg_cliente": "",
    "cfg_responsable": "",
    "cfg_tipo_limite": "Bilateral (± Tolerancia)",
    "cfg_tolerancia": 0.1,
    "cfg_LSL": -0.1,
    "cfg_USL": 0.1,
    "cfg_regla_key": "aceptacion_simple",
    "cfg_multiplicador": 1.0,
    "cfg_nivel_nombre": None,
    "cfg_k": 2.0,
    "cfg_origen": "✍️ Ingreso manual",
    "cfg_nivel_sel": "1·U  —  Riesgo < 2.5%  (Regla ILAC G8:2009)",
    "cfg_nivel_sel_nb": "1·U  —  Riesgo < 2.5%  (Regla ILAC G8:2009)",
    "cfg_multiplicador_nb": 1.0,
    "informe_docx_bytes": None,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

if st.session_state["catalogo"] is None:
    st.session_state["catalogo"] = cargar_catalogo()

# Cargar historial persistido si la sesión está vacía
if not st.session_state["historial"]:
    persistido = cargar_historial()
    if persistido:
        st.session_state["historial"] = persistido


# =============================================================================
# DICCIONARIOS DE NIVELES DE CONFIANZA (zona de seguridad w = r·U)
# =============================================================================

NIVELES_CONFIANZA = {
    "3·U  —  Riesgo < 1 ppm  (6 sigma)": 3.0,
    "1.5·U  —  Riesgo < 0.16%  (3 sigma)": 1.5,
    "1·U  —  Riesgo < 2.5%  (Regla ILAC G8:2009)": 1.0,
    "0.83·U  —  Riesgo < 5%  (ISO 14253-1:2017)": 0.83,
    "Personalizado": None,
}

NOMBRES_REGLA = {
    "aceptacion_simple": "Aceptación Simple (Binaria)",
    "binaria_zona_seguridad": "Binaria con Zona de Seguridad",
    "no_binaria_zona_seguridad": "No Binaria con Zona de Seguridad",
}


def get_pct_ref(mult: float | None) -> str:
    try:
        mult = float(mult)
    except (TypeError, ValueError):
        mult = 1.0
    if abs(mult - 0.83) < 0.01:
        return "5%"
    if abs(mult - 1.0) < 0.01:
        return "2.5%"
    if abs(mult - 1.5) < 0.01:
        return "0.16%"
    if abs(mult - 3.0) < 0.01:
        return "1 ppm"
    return "2.5%"


def pct_ref_num(pct_ref: str) -> float:
    if pct_ref == "1 ppm":
        return 0.0001
    return float(pct_ref.replace("%", ""))


def fmt_pct_valor(valor: float) -> str:
    if valor < 0.01:
        return f"{valor:.4g}%"
    return f"{valor:.2f}%"


def complemento_pct(pct_ref: str) -> str:
    if pct_ref == "1 ppm":
        return "≈ 100%"
    val = float(pct_ref.replace("%", ""))
    return f"{100 - val:.4g}%"


def _es_finito(valor: float | None) -> bool:
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return False
    return abs(valor) < INF


def _riesgos_exactos(row, cfg: dict) -> tuple[float, float]:
    valor = float(row.get("Valor Medido", 0.0))
    U = float(row.get("U", 0.0))
    LSL = cfg.get("LSL", -INF)
    USL = cfg.get("USL", INF)
    k = float(cfg.get("k", 2.0) or 2.0)

    pfa_vals = []
    if _es_finito(USL):
        pfa_vals.append(probabilidad_mas_alla(valor, float(USL), U, k) * 100)
    if _es_finito(LSL):
        pfa_vals.append(probabilidad_mas_alla_inferior(valor, float(LSL), U, k) * 100)
    pfa = max(pfa_vals) if pfa_vals else 0.0

    pfr_vals = []
    if _es_finito(USL) and (not _es_finito(LSL) or abs(valor - float(USL)) <= abs(valor - float(LSL))):
        pfr_vals.append((1 - probabilidad_mas_alla(valor, float(USL), U, k)) * 100)
    if _es_finito(LSL) and (not _es_finito(USL) or abs(valor - float(LSL)) < abs(valor - float(USL))):
        pfr_vals.append((1 - probabilidad_mas_alla_inferior(valor, float(LSL), U, k)) * 100)
    pfr = max(pfr_vals) if pfr_vals else 0.0
    return max(0.0, min(100.0, pfa)), max(0.0, min(100.0, pfr))


def _riesgo_texto(row, cfg: dict) -> str:
    decision = row.get("Decisión", row.get("DecisiÃ³n", ""))
    zona = str(row.get("Zona", "")).lower()
    regla = cfg.get("regla", "aceptacion_simple")
    pfa, pfr = _riesgos_exactos(row, cfg)

    if regla == "aceptacion_simple":
        return "PFA ≤ 50%" if decision == "Pasa" else "PFR ≤ 50%"

    if regla == "binaria_zona_seguridad":
        pct_ref = get_pct_ref(cfg.get("multiplicador") or 1.0)
        if decision == "Pasa":
            return f"PFA ≤ {pct_ref} (específicamente {fmt_pct_valor(pfa)})"
        if "conservador" in zona:
            return f"PFR entre aprox. {complemento_pct(pct_ref)} y 50% (específicamente {fmt_pct_valor(pfr)})"
        if "cerca" in zona:
            return f"PFR entre 50% y {pct_ref} (específicamente {fmt_pct_valor(pfr)})"
        if "claro" in zona:
            return f"PFR < {pct_ref} (específicamente {fmt_pct_valor(pfr)})"
        return f"PFR: {fmt_pct_valor(pfr)}"

    pct_ref = get_pct_ref(cfg.get("multiplicador") or 1.0)
    if decision == "Pasa":
        return f"PFA ≤ {pct_ref} (específicamente {fmt_pct_valor(pfa)})"
    if decision == "Pasa condicionalmente":
        return f"PFA entre {pct_ref} y 50% (específicamente {fmt_pct_valor(pfa)})"
    if decision == "No pasa condicionalmente":
        return f"PFR entre 50% y {pct_ref} (específicamente {fmt_pct_valor(pfr)})"
    if decision == "No pasa":
        return f"PFR < {pct_ref} (específicamente {fmt_pct_valor(pfr)})"
    return "—"


def _generar_bytes_informe(cfg: dict, df) -> bytes | None:
    """
    Genera los bytes del informe Word para un cfg y df dados.
    Reutilizable desde Resultados y desde la página de Informe.
    """
    try:
        LSL, USL, unidad = cfg["LSL"], cfg["USL"], cfg["unidad"]
        regla_actual = cfg.get("regla", "aceptacion_simple")

        fig_comp = grafico_comparativo(df, LSL, USL, unidad,
                                       titulo=cfg["nombre"],
                                       regla=regla_actual)
        grafico_bytes = None
        if fig_comp:
            buf_img = io.BytesIO()
            fig_comp.savefig(buf_img, format="png", dpi=150, bbox_inches="tight")
            grafico_bytes = buf_img.getvalue()
            plt.close(fig_comp)

        filas_informe = []
        for _, row in df.iterrows():
            decision = row["Decisión"]
            riesgo_str = _riesgo_texto(row, cfg)
            filas_informe.append({
                "etiqueta": row["Etiqueta"],
                "valor_medido": row["Valor Medido"],
                "U": row["U"],
                "decision": decision,
                "icono": row["Decision_Icono"],
                "zona": row["Zona"],
                "riesgo": riesgo_str,
                "PFA_min": row["PFA_min"], "PFA_max": row["PFA_max"],
                "PFR_min": row["PFR_min"], "PFR_max": row["PFR_max"],
                "AL_inf": row["AL_inf"], "AL_sup": row["AL_sup"],
            })

        cfg_informe = dict(cfg)
        cfg_informe["w"] = df["w"].iloc[0] if "w" in df.columns else None
        pct_ref = get_pct_ref(cfg.get("multiplicador") or 1.0)
        cfg_informe["riesgo_ref_text"] = pct_ref
        cfg_informe["riesgo_ref_pct"] = pct_ref_num(pct_ref)
        return generar_informe_docx(cfg_informe, filas_informe, grafico_bytes)
    except Exception as e:
        import traceback
        st.session_state["_ultimo_error_informe"] = traceback.format_exc()
        return None


# =============================================================================
# SIDEBAR — NAVEGACIÓN
# =============================================================================

with st.sidebar:
    st.markdown("## 📐 Regla de Decisión")
    st.caption("Conformidad Metrológica · ISO/IEC 17025")
    st.divider()
    pagina = st.radio(
        "Navegación",
        ["⚙️ Configuración", "📥 Datos de Medición", "📊 Resultados", "📄 Informe", "📜 Historial", "🗄️ Catálogo de Equipos"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Basado en ISO/IEC 17025:2017 · ILAC G8:2009 · ISO 14253-1:2017")

st.title("📐 Plataforma de Conformidad Metrológica — Regla de Decisión")
st.caption("Declaración de conformidad, análisis de riesgos (PFA/PFR) y reporte según ISO/IEC 17025:2017")
st.divider()


# =============================================================================
# PÁGINA 1: CONFIGURACIÓN
# =============================================================================

if pagina == "⚙️ Configuración":
    st.header("⚙️ Configuración del Ítem y la Regla de Decisión")

    ORIGENES_DATOS = [
        "✍️ Ingreso manual",
        "📋 Desde equipos registrados en MetriCore",
        "🗄️ Desde catálogo de equipos",
    ]
    origen_default = st.session_state.get("cfg_origen", "✍️ Ingreso manual")
    if origen_default not in ORIGENES_DATOS:
        origen_default = "✍️ Ingreso manual"

    origen = st.radio(
        "Origen de los datos del instrumento/ítem:",
        ORIGENES_DATOS,
        horizontal=True,
        index=ORIGENES_DATOS.index(origen_default),
    )
    st.session_state["cfg_origen"] = origen

    datos_catalogo = {}
    if origen == "📋 Desde equipos registrados en MetriCore":
        df_equipos = get_equipos()
        if df_equipos.empty:
            st.warning("No hay equipos registrados. Agregue primero un equipo en Ficha de equipos.")
            st.stop()

        opciones = {
            f"[{row['id']}] {row['nombre']}": row
            for _, row in df_equipos.iterrows()
        }
        seleccion = st.selectbox("Seleccione el equipo registrado:", list(opciones.keys()))
        equipo_reg = opciones[seleccion]

        nombre_instrumento = f"{equipo_reg['nombre']} ({equipo_reg['id']})"
        unidad = equipo_reg["unidad"] if pd.notna(equipo_reg["unidad"]) and equipo_reg["unidad"] else st.session_state.get("cfg_unidad", "unidad")
        tolerancia_reg = equipo_reg["tolerancia"]
        tiene_tolerancia_registrada = pd.notna(tolerancia_reg) and tolerancia_reg not in (None, "")
        tolerancia_default = (
            float(tolerancia_reg)
            if tiene_tolerancia_registrada
            else _ss_float("cfg_tolerancia", 0.1)
        )

        st.info(
            f"**Equipo:** {equipo_reg['nombre']}  |  "
            f"**Unidad:** {unidad or '—'}  |  "
            f"**Tolerancia / EMP registrado:** ±{tolerancia_default:g} {unidad or ''}"
        )
        if not tiene_tolerancia_registrada:
            st.warning(
                "Este equipo no tiene tolerancia / EMP registrada en su ficha. "
                "Se usa un valor editable de respaldo."
            )

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            nominal = st.number_input(
                "Valor nominal (referencia):",
                value=_ss_float("cfg_nominal", 0.0),
                format="%.6f",
                key="input_nominal_registrado",
            )
            cliente = st.text_input(
                "Cliente (opcional, para el informe):",
                value=st.session_state.get("cfg_cliente", ""),
                key="input_cliente",
            )
        with c2:
            tipo_limite = "Bilateral (± Tolerancia)"
            tolerancia = st.number_input(
                "Tolerancia / EMP tomada de ficha del equipo:",
                value=tolerancia_default,
                min_value=1e-9,
                format="%.6f",
                key=f"input_tolerancia_registrada_{equipo_reg['id']}",
            )
            responsable = st.text_input(
                "Responsable del análisis (opcional):",
                value=equipo_reg["responsable"] if pd.notna(equipo_reg["responsable"]) and equipo_reg["responsable"] else st.session_state.get("cfg_responsable", ""),
                key="input_responsable",
            )

        LSL = nominal - tolerancia
        USL = nominal + tolerancia
        st.info(f"**LSL = {LSL:.6g} {unidad}**  ·  **USL = {USL:.6g} {unidad}**")

    elif origen == "🗄️ Desde catálogo de equipos":
        catalogo = st.session_state["catalogo"]
        if not catalogo:
            st.warning(
                "El catálogo está vacío. Agregue equipos en la sección "
                "**🗄️ Catálogo de Equipos** del menú lateral."
            )
            st.stop()
        else:
            nombres = [e["nombre"] for e in catalogo]
            _cat_default = st.session_state.get("cfg_catalogo_sel", nombres[0])
            seleccion = st.selectbox(
                "Seleccione un equipo del catálogo:",
                nombres,
                index=nombres.index(_cat_default) if _cat_default in nombres else 0,
                key="input_catalogo_sel",
            )
            st.session_state["cfg_catalogo_sel"] = seleccion
            datos_catalogo = next(e for e in catalogo if e["nombre"] == seleccion)
            st.info(
                f"**Nombre:** {datos_catalogo.get('nombre','—')}  |  "
                f"**Unidad:** {datos_catalogo.get('unidad','—')}  |  "
                f"**Nominal:** {datos_catalogo.get('nominal','—')}  |  "
                f"**Tolerancia:** ±{datos_catalogo.get('tolerancia','—')}"
            )

        # Tomar todos los valores del catálogo directamente
        nombre_instrumento = datos_catalogo.get("nombre", "Ítem del catálogo")
        unidad             = datos_catalogo.get("unidad", "mm")
        nominal            = float(datos_catalogo.get("nominal", 0.0))
        tipo_limite        = datos_catalogo.get("tipo_limite", "Bilateral (± Tolerancia)")
        tolerancia         = float(datos_catalogo.get("tolerancia", 0.1)) if datos_catalogo.get("tolerancia") else None
        if tipo_limite == "Bilateral (± Tolerancia)" and tolerancia is not None:
            LSL = nominal - tolerancia
            USL = nominal + tolerancia
        elif tipo_limite == "Solo Máximo (USL)":
            USL = float(datos_catalogo.get("usl", nominal + 0.5))
            LSL = -INF
            tolerancia = None
        elif tipo_limite == "Solo Mínimo (LSL)":
            LSL = float(datos_catalogo.get("lsl", nominal - 0.5))
            USL = INF
            tolerancia = None
        else:
            LSL = nominal - (tolerancia or 0.1)
            USL = nominal + (tolerancia or 0.1)

        st.divider()
        # Solo pedir cliente y responsable (no hay datos del ítem que ingresar)
        c1, c2 = st.columns(2)
        with c1:
            cliente = st.text_input(
                "Cliente (opcional, para el informe):",
                value=st.session_state.get("cfg_cliente", ""),
                key="input_cliente",
            )
        with c2:
            responsable = st.text_input(
                "Responsable del análisis (opcional):",
                value=st.session_state.get("cfg_responsable", ""),
                key="input_responsable",
            )

    else:
        # ── Ingreso manual completo ──────────────────────────────────────────
        st.divider()
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("🔧 Datos del Ítem")
            nombre_instrumento = st.text_input(
                "Nombre / identificación:",
                value=st.session_state.get("cfg_nombre", "Ítem #1"),
                key="input_nombre",
            )
            unidad = st.text_input(
                "Unidad de medida:",
                value=st.session_state.get("cfg_unidad", "mm"),
                key="input_unidad",
            )
            nominal = st.number_input(
                "Valor nominal (referencia):",
                value=_ss_float("cfg_nominal", 0.0),
                format="%.6f",
                key="input_nominal",
            )
            cliente = st.text_input(
                "Cliente (opcional, para el informe):",
                value=st.session_state.get("cfg_cliente", ""),
                key="input_cliente",
            )
            responsable = st.text_input(
                "Responsable del análisis (opcional):",
                value=st.session_state.get("cfg_responsable", ""),
                key="input_responsable",
            )

        with c2:
            st.subheader("📏 Geometría de Límites")
            _tipos_limite = ["Bilateral (± Tolerancia)", "Solo Máximo (USL)", "Solo Mínimo (LSL)"]
            _tipo_default = st.session_state.get("cfg_tipo_limite", "Bilateral (± Tolerancia)")
            tipo_limite = st.selectbox(
                "Tipo de límite de especificación:",
                _tipos_limite,
                index=_tipos_limite.index(_tipo_default) if _tipo_default in _tipos_limite else 0,
                key="input_tipo_limite",
            )

            tolerancia = None
            if tipo_limite == "Bilateral (± Tolerancia)":
                tolerancia = st.number_input(
                    "Tolerancia (±):",
                    value=_ss_float("cfg_tolerancia", 0.1),
                    min_value=1e-9, format="%.6f",
                    key="input_tolerancia",
                )
                LSL = nominal - tolerancia
                USL = nominal + tolerancia
                st.info(f"**LSL = {LSL:.6g} {unidad}**  ·  **USL = {USL:.6g} {unidad}**")
            elif tipo_limite == "Solo Máximo (USL)":
                USL = st.number_input(
                    "Límite Superior de Tolerancia (USL):",
                    value=_ss_float("cfg_USL", nominal + 0.5), format="%.6f",
                    key="input_USL",
                )
                LSL = -INF
                st.info(f"**USL = {USL:.6g} {unidad}**  ·  Sin límite inferior")
            else:
                LSL = st.number_input(
                    "Límite Inferior de Tolerancia (LSL):",
                    value=_ss_float("cfg_LSL", nominal - 0.5), format="%.6f",
                    key="input_LSL",
                )
                USL = INF
                st.info(f"**LSL = {LSL:.6g} {unidad}**  ·  Sin límite superior")

    st.divider()
    st.subheader("⚖️ Regla de Decisión")

    rc1, rc2 = st.columns(2)
    with rc1:
        _reglas_list = list(NOMBRES_REGLA.keys())
        _regla_default = st.session_state.get("cfg_regla_key", "aceptacion_simple")
        regla_key = st.selectbox(
            "Tipo de regla de decisión:",
            _reglas_list,
            format_func=lambda k: NOMBRES_REGLA[k],
            index=_reglas_list.index(_regla_default) if _regla_default in _reglas_list else 0,
            key="input_regla_key",
        )

        descripciones = {
            "aceptacion_simple":
                "**AL = TL** (w = 0). Declaración **binaria**: Pasa / No pasa. "
                "Riesgo compartido — en el límite exacto, el riesgo puede llegar a 50%.",
            "binaria_zona_seguridad":
                "**AL = TL − w**. Declaración **binaria**: Pasa / No pasa, con un criterio "
                "de aceptación más estricto que el de tolerancia.",
            "no_binaria_zona_seguridad":
                "Declaración **no binaria**: Pasa / Pasa condicionalmente / No pasa condicionalmente / No pasa. "
                "La zona de transición w se configura según el nivel de confianza seleccionado.",
        }
        st.info(descripciones[regla_key])

    with rc2:
        nivel_nombre = None
        multiplicador = None

        if regla_key == "binaria_zona_seguridad":
            _nc_list = list(NIVELES_CONFIANZA.keys())
            _nc_default = st.session_state.get("cfg_nivel_sel", _nc_list[2])
            nivel_sel = st.selectbox(
                "Nivel de confianza (banda de guarda):", _nc_list,
                index=_nc_list.index(_nc_default) if _nc_default in _nc_list else 2,
                key="input_nivel_sel",
            )
            if NIVELES_CONFIANZA[nivel_sel] is not None:
                multiplicador = NIVELES_CONFIANZA[nivel_sel]
            else:
                multiplicador = st.slider(
                    "Multiplicador personalizado r (w = r·U):", 0.5, 3.0,
                    _ss_float("cfg_multiplicador", 1.0), 0.01,
                    key="input_mult",
                )
            nivel_nombre = nivel_sel
            st.info(f"La zona de seguridad se calculará como **w = {multiplicador:.2f} · U** para cada punto.")

        elif regla_key == "no_binaria_zona_seguridad":
            _nc_list_nb = list(NIVELES_CONFIANZA.keys())
            _nc_default_nb = st.session_state.get("cfg_nivel_sel_nb", _nc_list_nb[2])
            nivel_sel_nb = st.selectbox(
                "Nivel de confianza (banda de guarda):", _nc_list_nb,
                index=_nc_list_nb.index(_nc_default_nb) if _nc_default_nb in _nc_list_nb else 2,
                key="input_nivel_sel_nb",
            )
            if NIVELES_CONFIANZA[nivel_sel_nb] is not None:
                multiplicador = NIVELES_CONFIANZA[nivel_sel_nb]
            else:
                multiplicador = st.slider(
                    "Multiplicador personalizado r (w = r·U):", 0.5, 3.0,
                    _ss_float("cfg_multiplicador_nb", 1.0), 0.01,
                    key="input_mult_nb",
                )
            nivel_nombre = nivel_sel_nb
            st.session_state["cfg_nivel_sel_nb"] = nivel_sel_nb
            st.session_state["cfg_multiplicador_nb"] = multiplicador
            st.info(f"La zona de transición se calculará como **w = {multiplicador:.2f} · U** para cada punto.")
        else:
            st.info("No aplica zona de seguridad — el límite de aceptación coincide con el de tolerancia.")

    k_cobertura = st.number_input(
        "Factor de cobertura k de la incertidumbre expandida U (típicamente k=2):",
        value=_ss_float("cfg_k", 2.0),
        min_value=1.0, max_value=4.0, step=0.5,
        key="input_k",
    )

    errores_cfg = []
    errores_cfg += validar_texto(
        "Nombre / identificación del ítem",
        nombre_instrumento,
        requerido=True,
        no_solo_numeros=True,
    )
    errores_cfg += validar_unidad("Unidad de medida", unidad)
    errores_cfg += validar_texto("Cliente", cliente, no_solo_numeros=True)
    errores_cfg += validar_texto("Responsable del análisis", responsable, no_solo_numeros=True)
    errores_cfg += validar_numero("Valor nominal", nominal)
    errores_cfg += validar_numero("Factor de cobertura k", k_cobertura, minimo=1.0, permitir_cero=False)

    if tipo_limite == "Bilateral (± Tolerancia)":
        errores_cfg += validar_numero("Tolerancia / EMP", tolerancia, minimo=0.0, permitir_cero=False)
    elif tipo_limite == "Solo Máximo (USL)":
        errores_cfg += validar_numero("Límite superior USL", USL)
        if USL <= nominal:
            errores_cfg.append("El límite superior USL debe ser mayor que el valor nominal.")
    elif tipo_limite == "Solo Mínimo (LSL)":
        errores_cfg += validar_numero("Límite inferior LSL", LSL)
        if LSL >= nominal:
            errores_cfg.append("El límite inferior LSL debe ser menor que el valor nominal.")

    if mostrar_errores_validacion(errores_cfg):
        st.stop()

    # Persistir valores de configuración en session_state
    st.session_state["cfg_nombre"] = nombre_instrumento
    st.session_state["cfg_unidad"] = unidad
    st.session_state["cfg_nominal"] = nominal
    st.session_state["cfg_cliente"] = cliente
    st.session_state["cfg_responsable"] = responsable
    st.session_state["cfg_tipo_limite"] = tipo_limite
    st.session_state["cfg_tolerancia"] = tolerancia
    st.session_state["cfg_LSL"] = LSL
    st.session_state["cfg_USL"] = USL
    st.session_state["cfg_regla_key"] = regla_key
    st.session_state["cfg_multiplicador"] = multiplicador
    st.session_state["cfg_nivel_nombre"] = nivel_nombre
    st.session_state["cfg_k"] = k_cobertura
    if regla_key == "binaria_zona_seguridad":
        st.session_state["cfg_nivel_sel"] = nivel_sel

    # Guardar configuración
    st.session_state["config"] = {
        "nombre": nombre_instrumento,
        "unidad": unidad,
        "nominal": nominal,
        "cliente": cliente,
        "responsable": responsable,
        "tipo_limite": tipo_limite,
        "tolerancia": tolerancia,
        "LSL": LSL,
        "USL": USL,
        "regla": regla_key,
        "regla_nombre": NOMBRES_REGLA[regla_key],
        "multiplicador": multiplicador,
        "riesgo_ref_text": get_pct_ref(multiplicador or 1.0),
        "riesgo_ref_pct": pct_ref_num(get_pct_ref(multiplicador or 1.0)),
        "nivel_confianza_nombre": nivel_nombre,
        "k": k_cobertura,
        "es_no_binaria": regla_key == "no_binaria_zona_seguridad",
    }

    st.success("✅ Configuración guardada. Continúe a **📥 Datos de Medición**.")


# =============================================================================
# PÁGINA 2: DATOS DE MEDICIÓN
# =============================================================================

elif pagina == "📥 Datos de Medición":
    st.header("📥 Ingreso de Datos de Medición")

    cfg = st.session_state.get("config", {})
    if not cfg:
        st.warning("Primero complete la configuración en **⚙️ Configuración**.")
    else:
        st.markdown(
            f"**Ítem:** {cfg['nombre']}  |  **Regla:** {cfg['regla_nombre']}  |  "
            f"**Unidad:** {cfg['unidad']}"
        )
        st.divider()

        modo_entrada = st.radio(
            "Modo de ingreso de datos:",
            ["✍️ Manual (filas editables)", "📁 Cargar archivo CSV"],
            horizontal=True,
        )

        if modo_entrada == "✍️ Manual (filas editables)":
            st.caption(
                "Ingrese cada punto de medición. Use **Agregar punto** para añadir filas "
                "y el botón ❌ para eliminarlas."
            )

            nuevas_mediciones = []
            for idx, med in enumerate(st.session_state["mediciones"]):
                c0, c1, c2, c3 = st.columns([1.3, 1, 1, 0.3])
                etiqueta = c0.text_input(
                    "Etiqueta", value=med.get("etiqueta", f"Punto {idx+1}"),
                    key=f"etq_{idx}", label_visibility="collapsed" if idx > 0 else "visible",
                )
                valor = c1.number_input(
                    "Valor medido", value=float(med["valor_medido"]),
                    key=f"valor_{idx}", format="%.6f",
                    label_visibility="collapsed" if idx > 0 else "visible",
                )
                incertidumbre = c2.number_input(
                    "Incertidumbre U", value=float(med["incertidumbre"]),
                    min_value=0.0, key=f"inc_{idx}", format="%.6f",
                    label_visibility="collapsed" if idx > 0 else "visible",
                )
                eliminar = c3.button("❌", key=f"rm_{idx}")
                if not eliminar:
                    nuevas_mediciones.append({
                        "etiqueta": etiqueta, "valor_medido": float(valor),
                        "incertidumbre": float(incertidumbre),
                    })

            st.session_state["mediciones"] = nuevas_mediciones

            if st.button("➕ Agregar punto", use_container_width=True):
                n = len(st.session_state["mediciones"]) + 1
                st.session_state["mediciones"].append(
                    {"etiqueta": f"Punto {n}", "valor_medido": 0.0, "incertidumbre": 0.05}
                )
                st.rerun()

        else:
            st.caption(
                "El archivo CSV debe tener las columnas: `etiqueta, valor_medido, incertidumbre` "
                "(la etiqueta es opcional)."
            )
            archivo = st.file_uploader("Cargar archivo CSV:", type=["csv", "txt"])
            if archivo is not None:
                try:
                    df_carga = pd.read_csv(archivo)
                    df_carga.columns = [c.strip().lower() for c in df_carga.columns]
                    if "valor_medido" not in df_carga.columns or "incertidumbre" not in df_carga.columns:
                        st.error("El archivo debe contener al menos las columnas 'valor_medido' e 'incertidumbre'.")
                    else:
                        mediciones_csv = []
                        for i, row in df_carga.iterrows():
                            mediciones_csv.append({
                                "etiqueta": str(row.get("etiqueta", f"Punto {i+1}")),
                                "valor_medido": float(row["valor_medido"]),
                                "incertidumbre": float(row["incertidumbre"]),
                            })
                        st.session_state["mediciones"] = mediciones_csv
                        st.success(f"✅ Se cargaron {len(mediciones_csv)} puntos desde el archivo.")
                except Exception as exc:
                    st.error(f"Error al leer el archivo: {exc}")

        st.divider()
        if st.button("🔄 Procesar mediciones", type="primary", use_container_width=True):
            LSL, USL = cfg["LSL"], cfg["USL"]
            regla_key = cfg["regla"]
            k = cfg["k"]

            errores_med = []
            if not st.session_state["mediciones"]:
                errores_med.append("Debe ingresar al menos un punto de medición.")
            for idx, med in enumerate(st.session_state["mediciones"], start=1):
                errores_med += validar_texto(f"Etiqueta del punto {idx}", med.get("etiqueta"), requerido=True)
                errores_med += validar_numero(f"Valor medido del punto {idx}", med.get("valor_medido"))
                errores_med += validar_numero(
                    f"Incertidumbre U del punto {idx}",
                    med.get("incertidumbre"),
                    minimo=0.0,
                )

            if mostrar_errores_validacion(errores_med):
                st.stop()

            filas = []
            for med in st.session_state["mediciones"]:
                vm = med["valor_medido"]
                u = med["incertidumbre"]

                if regla_key == "binaria_zona_seguridad":
                    w = cfg["multiplicador"] * u
                elif regla_key == "no_binaria_zona_seguridad":
                    w = (cfg["multiplicador"] or 1.0) * u
                else:
                    w = 0.0

                pct_ref = get_pct_ref(cfg.get("multiplicador") or 1.0)
                resultado = evaluar_punto(
                    vm, u, LSL, USL, regla_key,
                    w=w, k=k,
                    riesgo_ref_pct=pct_ref_num(pct_ref),
                    riesgo_ref_text=pct_ref,
                )

                filas.append({
                    "Etiqueta": med["etiqueta"],
                    "Valor Medido": vm,
                    "U": u,
                    "Decisión": resultado.decision,
                    "Decision_Icono": resultado.icono,
                    "Zona": resultado.zona,
                    "PFA_min": resultado.pfa_min,
                    "PFA_max": resultado.pfa_max,
                    "PFR_min": resultado.pfr_min,
                    "PFR_max": resultado.pfr_max,
                    "AL_inf": resultado.AL_inf,
                    "AL_sup": resultado.AL_sup,
                    "w": resultado.w,
                    "Frase": resultado.frase,
                })

            st.session_state["df_resultados"] = pd.DataFrame(filas)
            st.success(f"✅ Se procesaron {len(filas)} puntos de medición.")


# =============================================================================
# PÁGINA 3: RESULTADOS
# =============================================================================

elif pagina == "📊 Resultados":
    st.header("📊 Resultados del Análisis")

    cfg = st.session_state.get("config", {})
    df = st.session_state.get("df_resultados")

    if df is None or df.empty or not cfg:
        st.info("Configure el ítem y procese mediciones primero.")
    else:
        LSL, USL, unidad = cfg["LSL"], cfg["USL"], cfg["unidad"]

        # ---- Tabla de resultados con color ----
        st.subheader("📋 Tabla de Resultados")

        def _riesgo_str(row):
            return _riesgo_texto(row, cfg)

        df_mostrar = df.copy()
        df_mostrar["Riesgo"] = df_mostrar.apply(_riesgo_str, axis=1)
        cols_ver = ["Etiqueta", "Valor Medido", "U", "Decisión", "Zona", "Riesgo"]

        def _colorear(col):
            return [
                f"background-color: #dcf5e3; color: {COLOR_VERDE};" if "✅" in str(v) else
                f"background-color: #fbe0dc; color: {COLOR_ROJO};" if "❌" in str(v) else
                f"background-color: #fcefd0; color: {COLOR_AMARILLO};" if "⚠️" in str(v) else ""
                for v in col
            ]

        styled = df_mostrar[cols_ver].style.apply(_colorear, subset=["Decisión"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # ---- Resumen de decisiones ----
        st.subheader("📌 Resumen de Decisiones")
        conteo = df["Decisión"].value_counts()
        total = len(df)
        cols_resumen = st.columns(5)
        cols_resumen[0].metric("📊 Total evaluadas", total)
        cols_resumen[1].metric("✅ Pasan", int(conteo.get("Pasa", 0)))
        cols_resumen[2].metric("⚠️ Pasan condicionalmente", int(conteo.get("Pasa condicionalmente", 0)))
        cols_resumen[3].metric("⚠️ No pasan condicionalmente", int(conteo.get("No pasa condicionalmente", 0)))
        cols_resumen[4].metric("❌ No pasan", int(conteo.get("No pasa", 0)))

        st.divider()

        # ---- Gráfico comparativo ----
        st.subheader("🗺️ Gráfico Comparativo de Zonas de Conformidad")
        df_graf = df.rename(columns={"Etiqueta": "Etiqueta"})
        fig_comp = grafico_comparativo(df_graf, LSL, USL, unidad, titulo=cfg["nombre"], regla=cfg.get("regla",""))
        if fig_comp:
            st.pyplot(fig_comp)
            buf = io.BytesIO()
            fig_comp.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            st.session_state["grafico_comparativo_bytes"] = buf.getvalue()
            st.download_button(
                "⬇️ Descargar gráfico comparativo (PNG)",
                data=buf.getvalue(), file_name="grafico_comparativo.png", mime="image/png",
            )

        st.divider()

        # ---- Gráfico individual ----
        st.subheader("🔍 Gráfico Individual por Punto")
        etiqueta_sel = st.selectbox("Seleccione un punto:", df["Etiqueta"].tolist())
        fila = df[df["Etiqueta"] == etiqueta_sel].iloc[0]

        from regla_decision.logica_rd import ResultadoEvaluacion
        resultado_sel = ResultadoEvaluacion(
            decision=fila["Decisión"], icono=fila["Decision_Icono"], zona=fila["Zona"],
            pfa_min=fila["PFA_min"], pfa_max=fila["PFA_max"],
            pfr_min=fila["PFR_min"], pfr_max=fila["PFR_max"],
            AL_inf=fila["AL_inf"], AL_sup=fila["AL_sup"], w=fila["w"],
        )
        resultado_sel.regla = cfg.get("regla", "")
        fig_ind = grafico_individual(
            fila["Valor Medido"], fila["U"], LSL, USL, resultado_sel, unidad,
            titulo=f"{cfg['nombre']} — {etiqueta_sel}",
        )
        st.pyplot(fig_ind)

        # Mostrar decisión y riesgo concordantes con la tabla
        _dec_ind   = fila["Decisión"]
        _icono_ind = fila["Decision_Icono"]
        _riesgo_ind = _riesgo_str(fila)
        _zona_ind  = fila["Zona"]
        st.markdown(
            f"{_icono_ind} **{_dec_ind}** &nbsp;·&nbsp; {_zona_ind}  \n"
            f"Riesgo asociado: **{_riesgo_ind}**"
        )

        st.divider()

        # ---- Guardar en historial ----
        if st.button("💾 Guardar este análisis en el historial", use_container_width=True):
            with st.spinner("Generando informe para el historial..."):
                _bytes_para_historial = _generar_bytes_informe(cfg, df)
            st.session_state["historial"].append({
                "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "item": cfg["nombre"],
                "regla": cfg["regla_nombre"],
                "n_puntos": len(df),
                "pasa": int(conteo.get("Pasa", 0)),
                "pasa_cond": int(conteo.get("Pasa condicionalmente", 0)),
                "no_pasa_cond": int(conteo.get("No pasa condicionalmente", 0)),
                "no_pasa": int(conteo.get("No pasa", 0)),
                "informe_bytes": _bytes_para_historial,
            })
            guardar_historial(st.session_state["historial"])
            st.toast("✅ Análisis e informe guardados en historial")

        # ---- Exportar CSV ----
        csv_export = df_mostrar[cols_ver].to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Exportar tabla para Excel (CSV)",
            data=csv_export, file_name=f"resultados_{cfg['nombre'].replace(' ', '_')}.csv",
            mime="text/csv; charset=utf-8",
        )


# =============================================================================
# PÁGINA 4: INFORME
# =============================================================================

elif pagina == "📄 Informe":
    st.header("📄 Informe de Declaración de Conformidad (Word)")

    cfg = st.session_state.get("config", {})
    df = st.session_state.get("df_resultados")

    if df is None or df.empty or not cfg:
        st.info("Configure el ítem y procese mediciones primero (ver pestañas anteriores).")
    else:
        st.markdown(
            "Genere un informe profesional en formato Word (.docx), listo para "
            "entregar al cliente, con la especificación aplicada, la regla de decisión, "
            "los resultados con su declaración de conformidad y riesgos asociados, y el "
            "gráfico de zonas de conformidad."
        )

        LSL, USL, unidad = cfg["LSL"], cfg["USL"], cfg["unidad"]

        if st.button("📄 Generar informe Word", type="primary", use_container_width=True):
            with st.spinner("Generando informe..."):
                docx_bytes = _generar_bytes_informe(cfg, df)
                st.session_state["informe_docx_bytes"] = docx_bytes
                if docx_bytes:
                    st.success("✅ Informe generado correctamente.")
                else:
                    st.error("Error al generar el informe.")
                    st.error(st.session_state.get("_ultimo_error_informe", "Sin detalles disponibles."))

        if st.session_state.get("informe_docx_bytes"):
            nombre_archivo = f"informe_conformidad_{cfg['nombre'].replace(' ', '_')}.docx"
            st.download_button(
                "⬇️ Descargar informe Word (.docx)",
                data=st.session_state["informe_docx_bytes"],
                file_name=nombre_archivo,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                type="primary",
            )


# =============================================================================
# PÁGINA 5: HISTORIAL
# =============================================================================

elif pagina == "📜 Historial":
    st.header("📜 Historial de Análisis")

    if not st.session_state["historial"]:
        st.info("Aún no hay análisis guardados. Procese mediciones y guárdelas desde **📊 Resultados**.")
    else:
        historial = st.session_state["historial"]

        st.subheader("📋 Registros guardados")

        # ── Encabezados ──────────────────────────────────────────────────────
        h_cols = st.columns([1.8, 1.6, 2.8, 0.7, 0.7, 0.9, 0.9, 0.7, 1.4])
        for hc, hd in zip(h_cols, [
            "Fecha", "Ítem", "Regla", "N pts",
            "Pasan", "Pasa cond.", "No pasa cond.", "No pasan", "Informe"
        ]):
            hc.markdown(f"<span style='font-weight:700;font-size:12px;color:#2c3e50'>{hd}</span>",
                        unsafe_allow_html=True)

        st.markdown("<hr style='margin:4px 0 8px 0;border-color:#e0e0e0'>", unsafe_allow_html=True)

        for i, entrada in enumerate(historial):
            cols = st.columns([1.8, 1.6, 2.8, 0.7, 0.7, 0.9, 0.9, 0.7, 1.4])
            cols[0].markdown(
                f"<span style='font-size:11.5px;color:#555'>{entrada.get('fecha','—')}</span>",
                unsafe_allow_html=True)
            cols[1].markdown(
                f"<span style='font-size:12px;font-weight:600;color:#2c3e50'>{entrada.get('item','—')}</span>",
                unsafe_allow_html=True)
            cols[2].markdown(
                f"<span style='font-size:11.5px;color:#444'>{entrada.get('regla','—')}</span>",
                unsafe_allow_html=True)
            cols[3].markdown(
                f"<div style='text-align:center;font-size:12px'>{entrada.get('n_puntos',0)}</div>",
                unsafe_allow_html=True)
            cols[4].markdown(
                f"<div style='text-align:center;font-size:12px;color:#1a7a40;font-weight:600'>{entrada.get('pasa',0)}</div>",
                unsafe_allow_html=True)
            cols[5].markdown(
                f"<div style='text-align:center;font-size:12px;color:#d35400;font-weight:600'>{entrada.get('pasa_cond',0)}</div>",
                unsafe_allow_html=True)
            cols[6].markdown(
                f"<div style='text-align:center;font-size:12px;color:#922b21;font-weight:600'>{entrada.get('no_pasa_cond',0)}</div>",
                unsafe_allow_html=True)
            cols[7].markdown(
                f"<div style='text-align:center;font-size:12px;color:#c0392b;font-weight:600'>{entrada.get('no_pasa',0)}</div>",
                unsafe_allow_html=True)

            # ── Botón de descarga inline ──────────────────────────────────────
            informe_bytes = entrada.get("informe_bytes")
            with cols[8]:
                if informe_bytes:
                    nombre_archivo = (
                        f"informe_{entrada.get('item','analisis').replace(' ','_')}"
                        f"_{entrada.get('fecha','').replace(':','').replace(' ','_')}.docx"
                    )
                    st.download_button(
                        "⬇️ .docx",
                        data=informe_bytes,
                        file_name=nombre_archivo,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl_inf_{i}",
                        use_container_width=True,
                    )
                else:
                    st.markdown(
                        "<span style='font-size:11px;color:#aaa'>Sin informe</span>",
                        unsafe_allow_html=True)

            st.markdown("<hr style='margin:4px 0;border-color:#f0f0f0'>", unsafe_allow_html=True)

        st.markdown("")

        # ── Acciones globales ─────────────────────────────────────────────────
        c1, c2 = st.columns(2)
        with c1:
            df_hist = pd.DataFrame([
                {k: v for k, v in e.items() if k != "informe_bytes"}
                for e in historial
            ])
            csv_hist = df_hist.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇️ Exportar historial para Excel (CSV)", data=csv_hist,
                file_name="historial_conformidad.csv", mime="text/csv; charset=utf-8",
                use_container_width=True,
            )
        with c2:
            if st.button("🗑️ Limpiar historial", use_container_width=True):
                st.session_state["historial"] = []
                guardar_historial([])
                st.rerun()


# =============================================================================
# PÁGINA 6: CATÁLOGO DE EQUIPOS
# =============================================================================

elif pagina == "🗄️ Catálogo de Equipos":
    st.header("🗄️ Catálogo de Equipos / Ítems Predefinidos")
    st.caption(
        "Guarde aquí los equipos que evalúa frecuentemente para reutilizar su "
        "especificación (nominal, tolerancia o límites) desde la pestaña de Configuración."
    )

    catalogo = st.session_state["catalogo"]

    with st.expander("➕ Agregar nuevo equipo al catálogo", expanded=len(catalogo) == 0):
        c1, c2 = st.columns(2)
        with c1:
            nombre_eq = st.text_input("Nombre del equipo:", key="cat_nombre")
            unidad_eq = st.text_input("Unidad:", key="cat_unidad", value="mm")
            tipo_eq = st.selectbox(
                "Tipo de límite:",
                ["Bilateral (± Tolerancia)", "Solo Máximo (USL)", "Solo Mínimo (LSL)"],
                key="cat_tipo",
            )
        with c2:
            nominal_eq = st.number_input("Valor nominal:", value=0.0, format="%.6f", key="cat_nominal")
            tol_eq = lsl_eq = usl_eq = None
            if tipo_eq == "Bilateral (± Tolerancia)":
                tol_eq = st.number_input("Tolerancia (±):", value=0.1, format="%.6f", key="cat_tol")
            elif tipo_eq == "Solo Máximo (USL)":
                usl_eq = st.number_input("USL:", value=0.5, format="%.6f", key="cat_usl")
            else:
                lsl_eq = st.number_input("LSL:", value=-0.5, format="%.6f", key="cat_lsl")

        if st.button("💾 Guardar equipo en catálogo", use_container_width=True):
            errores_cat = []
            errores_cat += validar_texto(
                "Nombre del equipo",
                nombre_eq,
                requerido=True,
                no_solo_numeros=True,
            )
            errores_cat += validar_unidad("Unidad", unidad_eq)
            errores_cat += validar_numero("Valor nominal", nominal_eq)
            if tipo_eq == "Bilateral (± Tolerancia)":
                errores_cat += validar_numero("Tolerancia", tol_eq, minimo=0.0, permitir_cero=False)
            elif tipo_eq == "Solo Máximo (USL)":
                errores_cat += validar_numero("USL", usl_eq)
                if usl_eq <= nominal_eq:
                    errores_cat.append("USL debe ser mayor que el valor nominal.")
            else:
                errores_cat += validar_numero("LSL", lsl_eq)
                if lsl_eq >= nominal_eq:
                    errores_cat.append("LSL debe ser menor que el valor nominal.")

            if mostrar_errores_validacion(errores_cat):
                st.stop()
            else:
                nuevo = {
                    "nombre": nombre_eq, "unidad": unidad_eq, "tipo_limite": tipo_eq,
                    "nominal": nominal_eq,
                }
                if tol_eq is not None:
                    nuevo["tolerancia"] = tol_eq
                if usl_eq is not None:
                    nuevo["usl"] = usl_eq
                if lsl_eq is not None:
                    nuevo["lsl"] = lsl_eq

                catalogo = [e for e in catalogo if e["nombre"] != nombre_eq]
                catalogo.append(nuevo)
                st.session_state["catalogo"] = catalogo
                guardar_catalogo(catalogo)
                st.success(f"✅ Equipo '{nombre_eq}' guardado en el catálogo.")
                st.rerun()

    st.divider()
    st.subheader("📋 Equipos guardados")
    if not catalogo:
        st.info("El catálogo está vacío.")
    else:
        for i, eq in enumerate(catalogo):
            c1, c2 = st.columns([5, 1])
            with c1:
                detalle = f"**{eq['nombre']}** — {eq.get('unidad','')} — {eq.get('tipo_limite','')}"
                if "tolerancia" in eq:
                    detalle += f" — nominal {eq.get('nominal')} ± {eq['tolerancia']}"
                elif "usl" in eq:
                    detalle += f" — USL {eq['usl']}"
                elif "lsl" in eq:
                    detalle += f" — LSL {eq['lsl']}"
                st.markdown(detalle)
            with c2:
                if st.button("🗑️ Eliminar", key=f"del_cat_{i}"):
                    catalogo.pop(i)
                    st.session_state["catalogo"] = catalogo
                    guardar_catalogo(catalogo)
                    st.rerun()


# =============================================================================
# PIE DE PÁGINA
# =============================================================================

st.divider()
st.caption(
    "Plataforma de Regla de Decisión en Metrología · "
    "Basada en ISO/IEC 17025:2017, ILAC G8:2009 e ISO 14253-1:2017"
)
