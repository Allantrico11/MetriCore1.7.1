import streamlit as st
from utils import aplicar_estilos, mostrar_errores_validacion, validar_numero, validar_texto, validar_unidad
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import get_equipos, get_calibraciones, insert_calibracion

st.set_page_config(page_title="Control de Calibraciones — MetriCore", layout="wide")
aplicar_estilos()
st.title("📈 Control de calibraciones")
st.caption("Gestión de resultados de calibración, errores e incertidumbres.")

equipos = get_equipos()

if equipos.empty:
    st.warning("No hay equipos registrados. Primero agrega equipos en Ficha de Equipos.")
    st.stop()

equipos["label"] = "[" + equipos["id"] + "] " + equipos["nombre"]
opciones = equipos["label"].tolist()
id_por_label = dict(zip(equipos["label"], equipos["id"]))

st.subheader("📊 Registro de resultados")
calibraciones = get_calibraciones()

if calibraciones.empty:
    st.info("No hay calibraciones registradas aún.")
else:
    df_mostrar = calibraciones[["equipo_id", "fecha", "proximo_vencimiento",
                                 "numero_certificado", "laboratorio",
                                 "incertidumbre", "error", "unidad", "metodo"]].copy()
    df_mostrar.columns = ["Equipo", "Fecha", "Próximo vencimiento",
                          "N° Certificado", "Laboratorio",
                          "Incertidumbre (U)", "Error", "Unidad", "Método"]
    st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

st.divider()
st.subheader("➕ Nueva calibración")

with st.container(border=True):

    if "cal_form_key" not in st.session_state:
        st.session_state.cal_form_key = 0

    equipo_label = st.selectbox("Equipo *", opciones, key=f"cal_equipo_{st.session_state.cal_form_key}")
    equipo_id = id_por_label[equipo_label]
    equipo_data = equipos[equipos["id"] == equipo_id].iloc[0]
    unidad_auto = equipo_data["unidad"] if equipo_data["unidad"] else ""
    st.info(f"Unidad del equipo: **{unidad_auto}**")

    with st.form(key=f"form_calibracion_{st.session_state.cal_form_key}"):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Datos del certificado**")
            fecha = st.date_input("Fecha de calibración *")
            proximo_venc = st.date_input("Próximo vencimiento *")
            numero_cert = st.text_input("N° de certificado", placeholder="Ej. CERT-2025-001")
            laboratorio = st.text_input("Laboratorio / Proveedor", placeholder="Ej. MetroTools S.A.")

        with col2:
            st.markdown("**Resultados de medición**")
            incertidumbre = st.number_input("Incertidumbre (U) *", min_value=0.0,
                                             step=0.0001, format="%.4f")
            error = st.number_input("Error instrumental *", step=0.0001, format="%.4f")
            unidad = st.text_input("Unidad", value=unidad_auto)
            metodo = st.selectbox("Método de evaluación", [
                "GUM (Guía para la expresión de incertidumbre)",
                "Monte Carlo",
                "Comparación directa",
                "Otro"
            ])

        col_r, col_c = st.columns(2)
        with col_r:
            submitted = st.form_submit_button("✅ Registrar calibración",
                                               type="primary", use_container_width=True)
        with col_c:
            cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)

        if submitted:
            errores = []
            errores += validar_texto("N° de certificado", numero_cert, requerido=True)
            errores += validar_texto("Laboratorio / Proveedor", laboratorio, requerido=True, no_solo_numeros=True)
            errores += validar_numero("Incertidumbre (U)", incertidumbre, minimo=0, permitir_cero=False)
            errores += validar_numero("Error instrumental", error)
            errores += validar_unidad("Unidad", unidad)
            if mostrar_errores_validacion(errores):
                st.stop()
            if incertidumbre == 0:
                st.error("La incertidumbre es obligatoria.")
            else:
                data = {
                    "equipo_id": equipo_id,
                    "fecha": str(fecha),
                    "proximo_vencimiento": str(proximo_venc),
                    "numero_certificado": numero_cert,
                    "laboratorio": laboratorio,
                    "incertidumbre": incertidumbre,
                    "error": error,
                    "unidad": unidad,
                    "metodo": metodo
                }
                insert_calibracion(data)
                st.success("✅ Calibración registrada correctamente.")
                st.session_state.cal_form_key += 1
                st.rerun()

        if cancelar:
            st.session_state.cal_form_key += 1
            st.rerun()

st.divider()
st.subheader("📉 Historial gráfico")

with st.container(border=True):
    equipo_graf_label = st.selectbox("Seleccionar equipo para graficar", opciones, key="graf")
    equipo_graf_id = id_por_label[equipo_graf_label]
    df_graf = get_calibraciones(equipo_graf_id)

    if not df_graf.empty:
        equipo_info = equipos[equipos["id"] == equipo_graf_id].iloc[0]
        tolerancia = equipo_info["tolerancia"]
        unidad_graf = equipo_info["unidad"]

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=df_graf["fecha"],
            y=df_graf["error"],
            mode="markers+lines",
            name="Error instrumental",
            error_y=dict(
                type="data",
                array=df_graf["incertidumbre"].tolist(),
                visible=True,
                color="#1A6FBF",
                thickness=2,
                width=6
            ),
            marker=dict(size=8, color="#1A6FBF"),
            line=dict(color="#1A6FBF")
        ))

        if tolerancia:
            fig.add_hline(y=tolerancia, line_dash="dash", line_color="red",
                          annotation_text=f"Tolerancia + ({tolerancia} {unidad_graf})")
            fig.add_hline(y=-tolerancia, line_dash="dash", line_color="red",
                          annotation_text=f"Tolerancia - (-{tolerancia} {unidad_graf})")

        fig.update_layout(
            title=f"Historial de error instrumental — {equipo_graf_id}",
            xaxis_title="Fecha",
            yaxis_title=f"Error ({unidad_graf})",
            plot_bgcolor="white",
            paper_bgcolor="white"
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(f"No hay calibraciones registradas para {equipo_graf_id}.")
