import re

import streamlit as st

def aplicar_estilos():
    st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        background-color: #0b2c40 !important;
    }
    [data-testid="stSidebar"] * {
        color: #E0F0ED !important;
    }
    [data-testid="stSidebarNav"] a {
        border-radius: 8px;
        padding: 6px 12px;
        margin: 2px 0;
    }
    [data-testid="stSidebarNav"] a:hover {
        background-color: #0a453c !important;
    }
    [data-testid="stSidebarNav"] a[aria-selected="true"] {
        background-color: #238d93 !important;
    }
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #2dc197;
        border-left: 5px solid #1469aa;
        border-radius: 8px;
        padding: 16px 20px;
    }
    [data-testid="stMetricLabel"] {
        color: #0a453c !important;
        font-size: 18px !important;
        font-weight: 500 !important;
    }
    [data-testid="stMetricValue"] {
        color: #0b2c40 !important;
        font-size: 36px !important;
        font-weight: 700 !important;
    }
    [data-testid="stDataFrame"] {
        background-color: #FFFFFF !important;
        border-radius: 8px !important;
        border: 1px solid #2dc197 !important;
    }
    [data-testid="stDataFrame"] iframe {
        background-color: #FFFFFF !important;
    }
    .stDataFrame {
        background-color: #FFFFFF !important;
    }
    </style>
    """, unsafe_allow_html=True)


def _texto(valor) -> str:
    return "" if valor is None else str(valor).strip()


def validar_requerido(nombre: str, valor) -> list[str]:
    if not _texto(valor):
        return [f"{nombre} es obligatorio."]
    return []


def validar_codigo(nombre: str, valor) -> list[str]:
    valor = _texto(valor)
    errores = validar_requerido(nombre, valor)
    if errores:
        return errores
    if not re.fullmatch(r"[A-Za-z0-9_.-]{2,40}", valor):
        return [f"{nombre} debe usar 2 a 40 caracteres: letras, números, guion, punto o guion bajo."]
    return []


def validar_texto(nombre: str, valor, requerido: bool = False,
                  no_solo_numeros: bool = False, max_len: int = 180) -> list[str]:
    valor = _texto(valor)
    if requerido and not valor:
        return [f"{nombre} es obligatorio."]
    if not valor:
        return []
    if len(valor) > max_len:
        return [f"{nombre} no debe superar {max_len} caracteres."]
    if any(ord(ch) < 32 and ch not in "\n\t" for ch in valor):
        return [f"{nombre} contiene caracteres no permitidos."]
    if no_solo_numeros and re.fullmatch(r"[-+]?\d+([.,]\d+)?", valor):
        return [f"{nombre} debe ser texto, no solo un número."]
    return []


def validar_unidad(nombre: str, valor, requerido: bool = True) -> list[str]:
    valor = _texto(valor)
    if requerido and not valor:
        return [f"{nombre} es obligatoria."]
    if not valor:
        return []
    if len(valor) > 20:
        return [f"{nombre} no debe superar 20 caracteres."]
    if not re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúÑñ°µΩ%/_. -]+", valor):
        return [f"{nombre} tiene caracteres no válidos para una unidad."]
    return []


def validar_numero(nombre: str, valor, minimo: float | None = None,
                   permitir_cero: bool = True) -> list[str]:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return [f"{nombre} debe ser numérico."]
    if numero != numero:
        return [f"{nombre} no puede ser NaN."]
    if minimo is not None and numero < minimo:
        return [f"{nombre} debe ser mayor o igual a {minimo}."]
    if not permitir_cero and numero == 0:
        return [f"{nombre} debe ser mayor que cero."]
    return []


def mostrar_errores_validacion(errores: list[str]) -> bool:
    for error in errores:
        st.error(f"❌ {error}")
    return bool(errores)
