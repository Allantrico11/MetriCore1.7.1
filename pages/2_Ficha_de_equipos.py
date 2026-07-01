import streamlit as st
import pandas as pd
from database import get_equipos, get_equipo_by_id, insert_equipo, update_equipo, delete_equipo, id_existe, UNIDADES_POR_TIPO
from utils import (
    aplicar_estilos,
    mostrar_errores_validacion,
    validar_codigo,
    validar_numero,
    validar_texto,
    validar_unidad,
)

st.set_page_config(page_title="Ficha de equipo — MetriCore", layout="wide")
aplicar_estilos()

PASSWORD_ADMIN = "metricore2026"

st.title("📋 Ficha de equipo")
st.caption("Registro y gestión del inventario de instrumentos de medición.")

TIPOS = list(UNIDADES_POR_TIPO.keys())

tab1, tab2 = st.tabs(["📄 Listado de equipos", "➕ Agregar nuevo"])

with tab1:
    equipos = get_equipos()
    if equipos.empty:
        st.info("No hay equipos registrados aún. Ve a 'Agregar nuevo' para comenzar.")
    else:
        busqueda = st.text_input("🔍 Buscar por nombre o ID", placeholder="Ej. BAL-001 o Balanza...")
        if busqueda:
            equipos = equipos[
                equipos["id"].str.contains(busqueda, case=False, na=False) |
                equipos["nombre"].str.contains(busqueda, case=False, na=False)
            ]

        columnas_mostrar = ["id", "nombre", "tipo", "marca", "modelo", "ubicacion", "estado", "proxima_calibracion"]
        nombres_columnas = {
            "id": "ID", "nombre": "Nombre", "tipo": "Tipo",
            "marca": "Marca", "modelo": "Modelo", "ubicacion": "Ubicación",
            "estado": "Estado", "proxima_calibracion": "Próxima calibración"
        }

        df_display = equipos[columnas_mostrar].rename(columns=nombres_columnas)
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        st.divider()

        equipos["label"] = "[" + equipos["id"] + "] " + equipos["nombre"]
        opciones_list = equipos["label"].tolist()
        id_por_label_list = dict(zip(equipos["label"], equipos["id"]))
        equipo_sel_label = st.selectbox("Seleccionar equipo", opciones_list, key="sel_equipo")
        equipo_sel = id_por_label_list[equipo_sel_label]

        col_ver, col_edit, col_del = st.columns(3)

        with col_ver:
            if st.button("👁️ Ver información completa", use_container_width=True):
                st.session_state.ver_equipo = equipo_sel
                st.session_state.pop("editar_equipo", None)
                st.session_state.pop("eliminar_equipo", None)

        with col_edit:
            if st.button("✏️ Editar equipo", use_container_width=True):
                st.session_state.solicitar_pass_editar = equipo_sel
                st.session_state.pop("ver_equipo", None)
                st.session_state.pop("eliminar_equipo", None)

        with col_del:
            if st.button("🗑️ Eliminar equipo", use_container_width=True, type="secondary"):
                st.session_state.solicitar_pass_eliminar = equipo_sel
                st.session_state.pop("ver_equipo", None)
                st.session_state.pop("editar_equipo", None)

        if "ver_equipo" in st.session_state and st.session_state.ver_equipo:
            eq = get_equipo_by_id(st.session_state.ver_equipo)
            if eq:
                with st.container(border=True):
                    st.subheader(f"📄 {eq['nombre']} — {eq['id']}")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Información general**")
                        st.write(f"- **Marca:** {eq['marca']}")
                        st.write(f"- **Modelo:** {eq['modelo']}")
                        st.write(f"- **N° Serie:** {eq['numero_serie']}")
                        st.write(f"- **Ubicación:** {eq['ubicacion']}")
                        st.write(f"- **Responsable:** {eq['responsable']}")
                        st.write(f"- **Estado:** {eq['estado']}")
                        st.markdown("**Servicio técnico**")
                        st.write(f"- **Proveedor:** {eq['proveedor']}")
                        st.write(f"- **Contacto:** {eq['contacto_proveedor']}")
                    with col2:
                        st.markdown("**Metrología**")
                        st.write(f"- **Rango máximo:** {eq['rango_max']} {eq['unidad']}")
                        st.write(f"- **Resolución:** {eq['resolucion']} {eq['unidad']}")
                        st.write(f"- **Tolerancia (EMP):** {eq['tolerancia']} {eq['unidad']}")
                        st.write(f"- **Última calibración:** {eq['ultima_calibracion']}")
                        st.write(f"- **Próxima calibración:** {eq['proxima_calibracion']}")
                        st.markdown("**Condiciones de uso**")
                        st.write(f"- **Condiciones ambientales:** {eq['condiciones_ambientales']}")
                        st.write(f"- **Instrucciones:** {eq['instrucciones_uso']}")
                    if st.button("Cerrar", key="cerrar_ver"):
                        del st.session_state.ver_equipo
                        st.rerun()

        if "solicitar_pass_editar" in st.session_state and st.session_state.solicitar_pass_editar:
            with st.container(border=True):
                st.warning("🔐 Se requiere contraseña de administrador para editar este equipo.")
                pass_editar = st.text_input("Contraseña", type="password", key="pass_editar_input")
                col_ok, col_can = st.columns(2)
                with col_ok:
                    if st.button("✅ Confirmar", key="confirmar_editar", use_container_width=True):
                        if pass_editar == PASSWORD_ADMIN:
                            st.session_state.editar_equipo = st.session_state.solicitar_pass_editar
                            del st.session_state.solicitar_pass_editar
                            st.rerun()
                        else:
                            st.error("❌ Contraseña incorrecta.")
                with col_can:
                    if st.button("Cancelar", key="cancelar_editar", use_container_width=True):
                        del st.session_state.solicitar_pass_editar
                        st.rerun()

        if "editar_equipo" in st.session_state and st.session_state.editar_equipo:
            eq = get_equipo_by_id(st.session_state.editar_equipo)
            if eq:
                with st.container(border=True):
                    st.subheader(f"✏️ Editando: {eq['nombre']} — {eq['id']}")
                    with st.form("form_editar"):
                        col1, col2 = st.columns(2)
                        with col1:
                            nombre = st.text_input("Nombre *", value=eq["nombre"])
                            tipo = st.selectbox("Tipo", TIPOS, index=TIPOS.index(eq["tipo"]) if eq["tipo"] in TIPOS else 0)
                            unidades_disp = UNIDADES_POR_TIPO[tipo]
                            unidad = st.selectbox("Unidad", unidades_disp, index=unidades_disp.index(eq["unidad"]) if eq["unidad"] in unidades_disp else 0)
                            ubicacion = st.text_input("Ubicación", value=eq["ubicacion"] or "")
                            responsable = st.text_input("Responsable", value=eq["responsable"] or "")
                            estado = st.selectbox("Estado", ["En servicio", "Fuera de servicio", "En mantenimiento", "En calibración"],
                                                  index=["En servicio", "Fuera de servicio", "En mantenimiento", "En calibración"].index(eq["estado"]) if eq["estado"] else 0)
                            proveedor = st.text_input("Proveedor", value=eq["proveedor"] or "")
                            contacto = st.text_input("Contacto proveedor", value=eq["contacto_proveedor"] or "")
                        with col2:
                            marca = st.text_input("Marca", value=eq["marca"] or "")
                            modelo = st.text_input("Modelo", value=eq["modelo"] or "")
                            serie = st.text_input("N° Serie", value=eq["numero_serie"] or "")
                            rango_max = st.number_input("Rango máximo", value=float(eq["rango_max"] or 0), step=0.1)
                            resolucion = st.number_input("Resolución", value=float(eq["resolucion"] or 0), step=0.001, format="%.4f")
                            tolerancia = st.number_input("Tolerancia (EMP)", value=float(eq["tolerancia"] or 0), step=0.001, format="%.4f")
                            condiciones_amb = st.text_area("Condiciones ambientales", value=eq["condiciones_ambientales"] or "")
                            instrucciones = st.text_area("Instrucciones de uso", value=eq["instrucciones_uso"] or "")

                        col_s, col_c = st.columns(2)
                        with col_s:
                            submitted = st.form_submit_button("💾 Guardar cambios", type="primary", use_container_width=True)
                        with col_c:
                            cancelar = st.form_submit_button("Cancelar", use_container_width=True)

                        if submitted:
                            errores = []
                            errores += validar_texto("Nombre", nombre, requerido=True, no_solo_numeros=True)
                            errores += validar_texto("Ubicación", ubicacion, no_solo_numeros=True)
                            errores += validar_texto("Responsable", responsable, no_solo_numeros=True)
                            errores += validar_texto("Proveedor", proveedor, no_solo_numeros=True)
                            errores += validar_texto("Marca", marca, no_solo_numeros=True)
                            errores += validar_texto("Modelo", modelo)
                            errores += validar_texto("Número de serie", serie)
                            errores += validar_numero("Rango máximo", rango_max, minimo=0)
                            errores += validar_numero("Resolución", resolucion, minimo=0)
                            errores += validar_numero("Tolerancia (EMP)", tolerancia, minimo=0)
                            errores += validar_unidad("Unidad", unidad)
                            if mostrar_errores_validacion(errores):
                                st.stop()
                            data = {
                                "id": eq["id"],
                                "nombre": nombre,
                                "tipo": tipo,
                                "marca": marca,
                                "modelo": modelo,
                                "numero_serie": serie,
                                "ubicacion": ubicacion,
                                "responsable": responsable,
                                "rango_max": rango_max,
                                "resolucion": resolucion,
                                "unidad": unidad,
                                "tolerancia": tolerancia,
                                "estado": estado,
                                "ultima_calibracion": eq["ultima_calibracion"],
                                "proxima_calibracion": eq["proxima_calibracion"],
                                "proveedor": proveedor,
                                "contacto_proveedor": contacto,
                                "condiciones_ambientales": condiciones_amb,
                                "instrucciones_uso": instrucciones
                            }
                            update_equipo(data)
                            st.success("✅ Equipo actualizado correctamente.")
                            del st.session_state.editar_equipo
                            st.rerun()

                        if cancelar:
                            del st.session_state.editar_equipo
                            st.rerun()

        if "solicitar_pass_eliminar" in st.session_state and st.session_state.solicitar_pass_eliminar:
            with st.container(border=True):
                st.error("⚠️ Esta acción eliminará el equipo permanentemente.")
                st.warning("🔐 Se requiere contraseña de administrador para continuar.")
                pass_eliminar = st.text_input("Contraseña", type="password", key="pass_eliminar_input")
                col_ok, col_can = st.columns(2)
                with col_ok:
                    if st.button("🗑️ Confirmar eliminación", key="confirmar_eliminar",
                                 type="secondary", use_container_width=True):
                        if pass_eliminar == PASSWORD_ADMIN:
                            equipo_a_eliminar = st.session_state.solicitar_pass_eliminar
                            delete_equipo(equipo_a_eliminar)
                            del st.session_state.solicitar_pass_eliminar
                            st.success(f"✅ Equipo {equipo_a_eliminar} eliminado.")
                            st.rerun()
                        else:
                            st.error("❌ Contraseña incorrecta.")
                with col_can:
                    if st.button("Cancelar", key="cancelar_eliminar", use_container_width=True):
                        del st.session_state.solicitar_pass_eliminar
                        st.rerun()

with tab2:
    st.subheader("Registrar nuevo equipo")

    if "form_key" not in st.session_state:
        st.session_state.form_key = 0

    tipo = st.selectbox("Tipo de equipo *", TIPOS, key=f"tipo_{st.session_state.form_key}")
    unidades_disp = UNIDADES_POR_TIPO[tipo]
    unidad = st.selectbox("Unidad *", unidades_disp, key=f"unidad_{st.session_state.form_key}")

    with st.form(key=f"form_equipo_{st.session_state.form_key}"):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Identificación**")
            id_eq = st.text_input("ID del equipo *", placeholder="Ej. BAL-001")
            nombre = st.text_input("Nombre *", placeholder="Ej. Balanza analítica")
            ubicacion = st.text_input("Ubicación", placeholder="Ej. Laboratorio de calidad")
            responsable = st.text_input("Responsable", placeholder="Nombre del responsable")
            st.markdown("**Estado y calibración**")
            estado = st.selectbox("Estado", ["En servicio", "Fuera de servicio", "En mantenimiento", "En calibración"])
            ultima_cal = st.date_input("Última calibración")
            proxima_cal = st.date_input("Próxima calibración")
            proveedor = st.text_input("Proveedor de calibración")
            contacto = st.text_input("Contacto del proveedor")

        with col2:
            st.markdown("**Especificaciones técnicas**")
            marca = st.text_input("Marca", placeholder="Ej. Mettler Toledo")
            modelo = st.text_input("Modelo", placeholder="Ej. XPR205")
            serie = st.text_input("Número de serie")
            rango_max = st.number_input("Rango máximo", min_value=0.0, step=0.1)
            resolucion = st.number_input("Resolución", min_value=0.0, step=0.001, format="%.4f")
            tolerancia = st.number_input("Tolerancia (EMP)", min_value=0.0, step=0.001, format="%.4f")
            st.markdown("**Condiciones y requisitos**")
            condiciones_amb = st.text_area("Condiciones ambientales", placeholder="Ej. 20 ± 5 °C, HR < 60%")
            instrucciones = st.text_area("Instrucciones generales de uso")

        col_add, col_can = st.columns(2)
        with col_add:
            submitted = st.form_submit_button("➕ Agregar equipo", type="primary", use_container_width=True)
        with col_can:
            cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)

        if submitted:
            errores = []
            errores += validar_codigo("ID del equipo", id_eq)
            errores += validar_texto("Nombre", nombre, requerido=True, no_solo_numeros=True)
            errores += validar_texto("Ubicación", ubicacion, no_solo_numeros=True)
            errores += validar_texto("Responsable", responsable, no_solo_numeros=True)
            errores += validar_texto("Proveedor de calibración", proveedor, no_solo_numeros=True)
            errores += validar_texto("Marca", marca, no_solo_numeros=True)
            errores += validar_texto("Modelo", modelo)
            errores += validar_texto("Número de serie", serie)
            errores += validar_numero("Rango máximo", rango_max, minimo=0)
            errores += validar_numero("Resolución", resolucion, minimo=0)
            errores += validar_numero("Tolerancia (EMP)", tolerancia, minimo=0)
            errores += validar_unidad("Unidad", unidad)
            if mostrar_errores_validacion(errores):
                st.stop()
            if not id_eq or not nombre:
                st.error("El ID y el nombre son obligatorios.")
            elif id_existe(id_eq):
                st.error(f"El ID '{id_eq}' ya está registrado. Usa un ID único.")
            else:
                data = {
                    "id": id_eq,
                    "nombre": nombre,
                    "tipo": tipo,
                    "marca": marca,
                    "modelo": modelo,
                    "numero_serie": serie,
                    "ubicacion": ubicacion,
                    "responsable": responsable,
                    "rango_max": rango_max,
                    "resolucion": resolucion,
                    "unidad": unidad,
                    "tolerancia": tolerancia,
                    "estado": estado,
                    "ultima_calibracion": str(ultima_cal),
                    "proxima_calibracion": str(proxima_cal),
                    "proveedor": proveedor,
                    "contacto_proveedor": contacto,
                    "condiciones_ambientales": condiciones_amb,
                    "instrucciones_uso": instrucciones
                }
                insert_equipo(data)
                st.success(f"✅ Equipo '{nombre}' registrado exitosamente.")
                st.session_state.form_key += 1
                st.rerun()

        if cancelar:
            st.session_state.form_key += 1
            st.rerun()
