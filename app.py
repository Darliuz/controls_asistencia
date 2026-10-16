from datetime import datetime, timezone, timedelta
import os
import pandas as pd
import streamlit as st
from supabase import create_client

# Configuración de página
st.set_page_config(
    page_title="Control Diario de Asistencia EPC", page_icon="📋", layout="wide"
)

EXCEL_DATA = "CONSOLIDADO EPC.xlsx"


# Inicializar cliente de Supabase mediante st.secrets
@st.cache_resource
def init_supabase():
  try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)
  except Exception as e:
    st.error(
        "Faltan las credenciales de Supabase en los secretos de Streamlit."
        f" Error: {e}"
    )
    return None


supabase = init_supabase()


@st.cache_data(ttl=1)
def cargar_datos_base():
  """Carga el archivo Excel principal con la data precargada"""
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

# Zona horaria de Venezuela (UTC-4)
venezuela_tz = timezone(timedelta(hours=-4))
fecha_hoy = datetime.now(venezuela_tz).strftime("%Y-%m-%d")
st.markdown(f"**Fecha actual:** `{fecha_hoy}`")

df_base = cargar_datos_base()

tab1, tab2 = st.tabs(
    ["📝 Registro de Asistencia", "📊 Consultar e Historial"]
)

with tab1:
  st.markdown("### Registro por Cédula")
  cedula_input = st.text_input(
      "Ingrese la Cédula de Identidad:", max_chars=12, key="cedula_reg"
  )

  if st.button("Registrar Asistencia", type="primary"):
    if not cedula_input.strip():
      st.warning("Por favor, ingrese un número de cédula válido.")
    elif df_base is None or "CEDULA" not in df_base.columns:
      st.error(
          "No se pudo cargar el archivo Excel base o falta la columna CEDULA."
      )
    else:
      cedula_limpia = cedula_input.strip()
      persona = df_base[df_base["CEDULA"] == cedula_limpia]

      if persona.empty:
        st.error(
            f"La cédula **{cedula_limpia}** no se encuentra registrada en la"
            " base de datos (Excel)."
        )
      else:
        # Extraer campos buscando nombres aproximados de columnas en el Excel
        def obtener_valor_columna(patrones, predeterminado="N/A"):
          col = next(
              (
                  c
                  for c in df_base.columns
                  if any(p in c for p in patrones)
              ),
              None,
          )
          if col and not pd.isna(persona.iloc[0][col]):
            return str(persona.iloc[0][col]).strip()
          return predeterminado

        nombre_persona = obtener_valor_columna(
            ["NOMBRE", "APELLIDO", "NOMBRES"], "Sin Nombre"
        )
        municipio = obtener_valor_columna(["MUNICIPIO"], "N/A")
        parroquia = obtener_valor_columna(["PARROQUIA"], "N/A")
        comision = obtener_valor_columna(["COMISION", "COMISIÓN"], "N/A")
        
        # Hora ajustada para la zona horaria de Venezuela
        hora_actual = datetime.now(venezuela_tz).strftime("%H:%M:%S")

        # Verificar duplicados en Supabase para el día de hoy
        duplicado = False
        if supabase:
          try:
            res = (
                supabase.table("registro_asistencias")
                .select("*")
                .eq("CEDULA", cedula_limpia)
                .eq("FECHA", fecha_hoy)
                .execute()
            )
            if res.data and len(res.data) > 0:
              duplicado = True
          except Exception as ex:
            st.warning(f"No se pudo verificar duplicados en la nube: {ex}")

        if duplicado:
          st.warning(
              f"⚠️ La cédula **{cedula_limpia}** ({nombre_persona}) ya tiene un"
              f" registro de asistencia para el día de hoy ({fecha_hoy})."
          )
        else:
          # Guardar registro en Supabase con todos los campos y hora correcta
          if supabase:
            try:
              nuevo_registro = {
                  "CEDULA": cedula_limpia,
                  "NOMBRE": nombre_persona,
                  "MUNICIPIO": municipio,
                  "PARROQUIA": parroquia,
                  "COMISION": comision,
                  "FECHA": fecha_hoy,
                  "HORA": hora_actual,
              }
              supabase.table("registro_asistencias").insert(
                  nuevo_registro
              ).execute()
              st.success(
                  f"✅ ¡Asistencia registrada con éxito para **{nombre_persona}**"
                  f" (Cédula: {cedula_limpia}) a las {hora_actual}!"
              )
            except Exception as err:
              st.error(f"Error al guardar en Supabase: {err}")
          else:
            st.error("No hay conexión con la base de datos en la nube.")

with tab2:
  st.markdown("### Historial de Asistencias Registradas")

  if not supabase:
    st.error("No hay conexión con Supabase configurada.")
  else:
    try:
      response = (
          supabase.table("registro_asistencias")
          .select("*")
          .order("FECHA", desc=True)
          .order("HORA", desc=True)
          .execute()
      )
      data = response.data

      if not data:
        st.info(
            "Aún no hay registros de asistencia guardados en la base de datos."
        )
      else:
        df_asist = pd.DataFrame(data)
        df_asist["FECHA_DT"] = pd.to_datetime(df_asist["FECHA"], errors="coerce")

        st.markdown("#### 📅 Seleccionar Rango de Fechas")
        col1, col2 = st.columns(2)

        with col1:
          fecha_inicio = st.date_input(
              "Fecha Inicial:", value=pd.to_datetime("2026-10-05")
          )
        with col2:
          fecha_fin = st.date_input(
              "Fecha Final:", value=pd.to_datetime("2026-10-11")
          )

        mask = (df_asist["FECHA_DT"].dt.date >= fecha_inicio) & (
            df_asist["FECHA_DT"].dt.date <= fecha_fin
        )
        df_filtrado = df_asist[mask].drop(
            columns=["FECHA_DT", "id", "created_at"], errors="ignore"
        )

        st.markdown(
            f"**Mostrando {len(df_filtrado)} registro(s) entre el"
            f" {fecha_inicio} y el {fecha_fin}:**"
        )
        st.dataframe(df_filtrado, use_container_width=True)

        st.download_button(
            label="📥 Descargar reporte del rango (CSV)",
            data=df_filtrado.to_csv(index=False).encode("utf-8"),
            file_name=f"asistencias_{fecha_inicio}_al_{fecha_fin}.csv",
            mime="text/csv",
        )
    except Exception as e:
      st.error(f"Error al consultar el historial en Supabase: {e}")
