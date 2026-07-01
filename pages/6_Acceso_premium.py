import streamlit as st
from utils import aplicar_estilos

st.set_page_config(page_title="Acceso a Plan Premium — MetriCore", layout="wide")
aplicar_estilos()
st.title("🔒 Acceso a Plan Premium")
st.caption("Desbloquea las herramientas avanzadas de análisis metrológico.")

CODIGOS_VALIDOS = ["METRO2026", "UCR-METRO", "PREMIUM01"]

if "premium_activo" not in st.session_state:
    st.session_state.premium_activo = False

if not st.session_state.premium_activo:
    col1, col2 = st.columns([1, 1])

    with col1:
        with st.container(border=True):
            st.subheader("🔑 Ingresar código de acceso")
            st.caption("Ingresa el código que recibiste al adquirir el Plan Premium.")

            codigo = st.text_input(
                "Código premium",
                placeholder="Ej. METRO2026",
                type="password"
            )

            if st.button("🚀 Desbloquear Plan Premium", type="primary", use_container_width=True):
                if codigo.strip() in CODIGOS_VALIDOS:
                    st.session_state.premium_activo = True
                    st.success("✅ ¡Plan Premium activado correctamente!")
                    st.rerun()
                else:
                    st.error("❌ Código inválido. Verifica el código o contáctanos.")

            st.divider()
            st.markdown("📞 **¿No tienes un código?**")
            st.markdown("Contáctanos vía WhatsApp al **8888-8888** para adquirir el Plan Premium.")

    with col2:
        with st.container(border=True):
            st.subheader("📦 ¿Qué incluye el Plan Premium?")

            with st.container(border=True):
                st.markdown("📊 **Regla de decisión**")
                st.caption("Evaluación de conformidad mediante criterios metrológicos formales compatibles con normas internacionales.")

            with st.container(border=True):
                st.markdown("📅 **Intervalos de calibración**")
                st.caption("Análisis de intervalos considerando criticidad, desempeño histórico y requerimientos metrológicos.")

else:
    with st.container(border=True):
        st.success("✅ Plan Premium activo — Tienes acceso a todos los módulos avanzados.")
        st.markdown("Puedes acceder a las herramientas premium desde el menú lateral:")
        st.markdown("- 📊 Regla de decisión")
        st.markdown("- 📅 Intervalos de calibración")
        st.divider()
        if st.button("🔓 Cerrar sesión premium", type="secondary"):
            st.session_state.premium_activo = False
            st.rerun()
