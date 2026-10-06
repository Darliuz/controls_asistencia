import streamlit as st
import pandas as pd
import os
from datetime import datetime

st.set_page_config(
    page_title="Control de Asistencia EPC",
    page_icon="📋",
    layout="centered"
)

EXCEL_DATA = "CONSOLIDADO EPC.xlsx"
ASISTENCIA_FILE = "registro_asistencias.csv"

@st.cache_data(ttl=1)
def cargar_datos_base():
  """Carga el archivo Excel principal con la data precargada sin bloqueos"""
  try:
    if not os.path.exists(EXCEL_DATA):
      return None
    df = pd.read_excel(EXCEL_DATA, sheet_name="EQUIPO POLITICO", header=1)
    df.columns = [str(c).strip().upper() for c in df.columns]

    if "CEDULA" in df.columns:
      df["CEDULA"] = (
          df["CEDULA"].astype(str).str.split(".").str[0].str.strip()
      )
    return df
  except Exception as e:
    st.error(f"Error al cargar el archivo Excel base: {e}")
    return None
      
st.title("📋 Control Diario de Asistencia EPC")
fecha_hoy = datetime.now().strftime("%Y-%m-%d")
st.markdown(f"**Fecha actual:** `{fecha_hoy}`")

df_base = cargar_datos_base()

# Formulario de registro por cédula
with st.form("form_asistencia", clear_on_submit=True):
    cedula = st.text_input("Número de Cédula:", placeholder="Ej. 12345678")
    submit = st.form_submit_button("Registrar Asistencia", use_container_width=True)

if submit:
    cedula = cedula.strip()
    if not cedula:
        st.warning("⚠️ Ingrese un número de cédula válido.")
    elif df_base.empty:
        st.error("❌ No se encontró el archivo de base de datos (`CONSOLIDADO EPC.xlsx`).")
    else:
        persona = df_base[df_base["CEDULA"] == cedula]
        if persona.empty:
            st.error(f"❌ La cédula '{cedula}' no está registrada en el archivo base.")
        else:
            row = persona.iloc[0]
            nombre = row.get("NOMBRE Y APELLIDO", "N/D")
            municipio = row.get("MUNICIPIO", "N/D")
            parroquia = row.get("PARroquia", row.get("PARROQUIA", "N/D"))
            comision = row.get("COMISION", "N/D")
            
            hora_actual = datetime.now().strftime("%H:%M:%S")
            
            # Validar si ya registró hoy
            ya_asistio = False
            if os.path.exists(ASISTENCIA_FILE):
                df_asist = pd.read_csv(ASISTENCIA_FILE, dtype=str)
                if not df_asist.empty:
                    duplicado = df_asist[(df_asist["CEDULA"] == cedula) & (df_asist["FECHA"] == fecha_hoy)]
                    if not duplicado.empty:
                        ya_asistio = True
                        
            if ya_asistio:
                st.warning(f"⚠️ AVISO: {nombre} (Cédula: {cedula}) ya tenía registrada su asistencia hoy.")
            else:
                nuevo_reg = {
                    "CEDULA": cedula,
                    "NOMBRE": nombre,
                    "MUNICIPIO": municipio,
                    "PARROQUIA": parroquia,
                    "COMISION": comision,
                    "FECHA": fecha_hoy,
                    "HORA": hora_actual
                }
                df_nuevo = pd.DataFrame([nuevo_reg])
                if not os.path.exists(ASISTENCIA_FILE):
                    df_nuevo.to_csv(ASISTENCIA_FILE, index=False)
                else:
                    df_nuevo.to_csv(ASISTENCIA_FILE, mode="a", header=False, index=False)
                st.success(f"✅ ¡Asistencia Registrada! -> **{nombre}** ({comision}) a las {hora_actual}")

st.divider()

# Historial
st.subheader("📊 Historial de Asistencias")
if os.path.exists(ASISTENCIA_FILE):
    df_asist = pd.read_csv(ASISTENCIA_FILE, dtype=str)
    if not df_asist.empty:
        # Filtro de fecha
        fechas_disponibles = sorted(df_asist["FECHA"].unique(), reverse=True)
        fecha_filtro = st.selectbox("Filtrar por fecha:", fechas_disponibles)
        
        df_filtrado = df_asist[df_asist["FECHA"] == fecha_filtro]
        st.dataframe(df_filtrado.iloc[::-1], use_container_width=True)
        
        # Botón para descargar CSV
        csv = df_filtrado.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar CSV de este día",
            data=csv,
            file_name=f"asistencia_{fecha_filtro}.csv",
            mime="text/csv"
        )
    else:
        st.info("Aún no hay registros guardados.")
else:
    st.info("Aún no hay registros de asistencia.")
