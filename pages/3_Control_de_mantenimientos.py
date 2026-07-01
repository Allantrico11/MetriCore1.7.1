import streamlit as st
from utils import aplicar_estilos, mostrar_errores_validacion, validar_texto
import pandas as pd
from database import get_equipos, get_mantenimientos, insert_mantenimiento

st.set_page_config(page_title="Control de Mantenimientos — MetriCore", layout="wide")
aplicar_estilos()
st.title("🔧 Control de mantenimientos")
st.caption("Registro y seguimiento de actividades preventivas y correctivas.")

equipos = get_equipos()

if equipos.empty:
    st.warning("No hay equipos registrados. Primero agrega equipos en Ficha de Equipos.")
    st.stop()

equipos["label"] = "[" + equipos["id"] + "] " + equipos["nombre"]
opciones = equipos["label"].tolist()
id_por_label = dict(zip(equipos["label"], equipos["id"]))

col_izq, col_der = st.columns([1, 2])

with col_izq:
    with st.container(border=True):
        st.subheader("➕ Nuevo registro")
        with st.form("form_mantenimiento", clear_on_submit=True):
            equipo_label = st.selectbox("Equipo *", opciones)
            tipo = st.selectbox("Tipo *", ["Preventivo", "Correctivo", "Predictivo", "Calibración"])
            fecha = st.date_input("Fecha de realización *")
            descripcion = st.text_area("Descripción de la actividad *",
                                       placeholder="Ej. Limpieza, ajuste, reemplazo de piezas...")
            responsable = st.text_input("Responsable *", placeholder="Técnico o proveedor")
            proximo = st.date_input("Próximo mantenimiento (sugerido)")

            col_g, col_c = st.columns(2)
            with col_g:
                submitted = st.form_submit_button("💾 Guardar registro", type="primary", use_container_width=True)
            with col_c:
                cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)

            if submitted:
                errores = []
                errores += validar_texto("Descripción de la actividad", descripcion, requerido=True, no_solo_numeros=True, max_len=600)
                errores += validar_texto("Responsable", responsable, requerido=True, no_solo_numeros=True)
                if mostrar_errores_validacion(errores):
                    st.stop()
                if not descripcion or not responsable:
                    st.error("La descripción y el responsable son obligatorios.")
                else:
                    data = {
                        "equipo_id": id_por_label[equipo_label],
                        "tipo": tipo,
                        "fecha": str(fecha),
                        "descripcion": descripcion,
                        "responsable": responsable,
                        "proximo_mantenimiento": str(proximo)
                    }
                    insert_mantenimiento(data)
                    st.success("✅ Mantenimiento registrado correctamente.")

            if cancelar:
                st.info("Registro cancelado.")

with col_der:
    with st.container(border=True):
        st.subheader("📋 Historial de actividades")
        filtro_label = st.selectbox("Filtrar por equipo", ["Todos los equipos"] + opciones)

        if filtro_label == "Todos los equipos":
            df = get_mantenimientos()
        else:
            df = get_mantenimientos(id_por_label[filtro_label])

        if df.empty:
            st.info("No hay registros de mantenimiento aún.")
        else:
            df_mostrar = df[["equipo_id", "tipo", "fecha", "descripcion", "responsable", "proximo_mantenimiento"]].copy()
            df_mostrar.columns = ["Equipo", "Tipo", "Fecha", "Descripción", "Responsable", "Próximo mantenimiento"]
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

        st.caption("En versiones futuras este módulo incluirá alertas automáticas por correo.")
