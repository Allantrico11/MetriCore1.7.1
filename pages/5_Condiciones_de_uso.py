import streamlit as st
from utils import aplicar_estilos, mostrar_errores_validacion, validar_texto
from database import get_equipos, get_condiciones, save_condiciones

st.set_page_config(page_title="Condiciones de Uso — MetriCore", layout="wide")
aplicar_estilos()
st.title("✅ Condiciones de uso")
st.caption("Definición de requisitos ambientales, operativos y de trazabilidad — ISO/IEC 17025.")

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
        st.subheader("🔍 Seleccionar equipo")
        equipo_label = st.selectbox("Equipo", opciones)
        equipo_id = id_por_label[equipo_label]
        equipo_data = equipos[equipos["id"] == equipo_id].iloc[0]

        st.markdown(f"**ID:** {equipo_data['id']}")
        st.markdown(f"**Nombre:** {equipo_data['nombre']}")
        st.markdown(f"**Ubicación:** {equipo_data['ubicacion']}")
        st.markdown(f"**Estado:** {equipo_data['estado']}")
        st.markdown(f"**Tipo:** {equipo_data['tipo']}")

with col_der:
    condiciones = get_condiciones(equipo_id)

    with st.container(border=True):
        st.subheader("📋 Ficha de condiciones de uso")

        with st.form("form_condiciones", clear_on_submit=False):

            with st.expander("🌡️ Condiciones ambientales y operativas", expanded=True):
                rango_op = st.text_area(
                    "Rango y condiciones de operación",
                    value=condiciones.get("rango_operacion", ""),
                    placeholder="Ej. 20 ± 5 °C, HR < 60%"
                )
                limitaciones = st.text_area(
                    "Limitaciones del equipo",
                    value=condiciones.get("limitaciones", ""),
                    placeholder="Ej. No exponer a luz solar directa"
                )

            with st.expander("📄 Procedimientos y verificaciones", expanded=False):
                procedimiento = st.text_area(
                    "Procedimiento de uso (referencia)",
                    value=condiciones.get("procedimiento_uso", ""),
                    placeholder="Ej. Verificación diaria de cero"
                )
                verificaciones = st.text_area(
                    "Verificaciones previas al uso",
                    value=condiciones.get("verificaciones_previas", ""),
                    placeholder="Ej. Bloques patrón, nivel de burbuja"
                )

            with st.expander("📦 Almacenamiento y trazabilidad", expanded=False):
                almacenamiento = st.text_area(
                    "Requisitos de almacenamiento",
                    value=condiciones.get("requisitos_almacenamiento", ""),
                    placeholder="Ej. Estuche rígido, libre de vibraciones"
                )
                trazabilidad = st.text_area(
                    "Requisitos de trazabilidad",
                    value=condiciones.get("requisitos_trazabilidad", ""),
                    placeholder="Ej. Patrones nacionales, CENAM"
                )

            col_g, col_c = st.columns(2)
            with col_g:
                submitted = st.form_submit_button("💾 Guardar condiciones",
                                                   type="primary", use_container_width=True)
            with col_c:
                cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)

            if submitted:
                errores = []
                errores += validar_texto("Rango y condiciones de operación", rango_op, max_len=700)
                errores += validar_texto("Limitaciones del equipo", limitaciones, max_len=700)
                errores += validar_texto("Procedimiento de uso", procedimiento, max_len=900)
                errores += validar_texto("Verificaciones previas", verificaciones, max_len=900)
                errores += validar_texto("Requisitos de almacenamiento", almacenamiento, max_len=700)
                errores += validar_texto("Requisitos de trazabilidad", trazabilidad, max_len=700)
                if mostrar_errores_validacion(errores):
                    st.stop()
                data = {
                    "equipo_id": equipo_id,
                    "rango_operacion": rango_op,
                    "limitaciones": limitaciones,
                    "procedimiento_uso": procedimiento,
                    "verificaciones_previas": verificaciones,
                    "requisitos_almacenamiento": almacenamiento,
                    "requisitos_trazabilidad": trazabilidad
                }
                save_condiciones(data)
                st.success("✅ Condiciones guardadas correctamente.")
                st.rerun()

            if cancelar:
                st.info("Cambios cancelados.")
                st.rerun()
