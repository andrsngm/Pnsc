import os
import subprocess
import sys

# --- BLOQUE DE AUTOPREPARACIÓN ---
def instalar_dependencias():
    try:
        import streamlit, pandas, sqlalchemy, openpyxl, altair
    except ImportError:
        subprocess.call([sys.executable, "-m", "pip", "install", "streamlit", "pandas", "sqlalchemy", "openpyxl", "altair"])

instalar_dependencias()

import streamlit as st
import pandas as pd
import altair as alt
from sqlalchemy import create_engine, text
from datetime import datetime
import pestaña_busqueda as pb  # Importación del archivo externo

# --- FUNCIONES DE FORMATO REGIONAL (Miles: . | Decimales: ,) ---
def formato_entero(valor):
    if pd.isna(valor) or valor == "": return "0"
    try:
        return f"{int(valor):,}".replace(",", ".")
    except:
        return "0"

def formato_decimal(valor):
    if pd.isna(valor): return "0,00"
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- LÓGICA DE BASE DE DATOS ---
def obtener_conexion(nombre_db):
    return create_engine(f'sqlite:///{nombre_db}')

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Consolidador PNSC Pro", layout="wide", page_icon="📊")

# Sidebar - Configuración
st.sidebar.header("⚙️ Configuración")
db_name = st.sidebar.text_input("Archivo BD", "base_datos_pnsc.db")
tabla_name = st.sidebar.text_input("Tabla", "consolidado_total")
columna_id = st.sidebar.text_input("Columna ID (Cédula)", "cedula")

st.sidebar.subheader("📅 Cronología")
col_fecha = st.sidebar.text_input("Columna de Fecha", "fecha")
col_ente = st.sidebar.text_input("Columna Ente / Institución", "institucion")

st.sidebar.subheader("🗂️ Jerarquía")
col_sub1 = st.sidebar.text_input("Nivel 1", "SubCatg1")
col_sub2 = st.sidebar.text_input("Nivel 2", "SubCatg2")
col_sub3 = st.sidebar.text_input("Nivel 3", "SubCatg3")
col_sub4 = st.sidebar.text_input("Nivel 4", "SubCatg4")

st.sidebar.subheader("📍 Geografía")
col_estado = st.sidebar.text_input("Columna Estado", "estado")
col_municipio = st.sidebar.text_input("Columna Municipio", "municipio")
col_parroquia = st.sidebar.text_input("Columna Parroquia", "parroquia")

if not db_name.endswith('.db'): db_name += '.db'
engine = obtener_conexion(db_name)

# --- FILTRO GLOBAL POR AÑO ---
st.sidebar.divider()
try:
    with engine.connect() as conn:
        años_disponibles = conn.execute(text(f'SELECT DISTINCT strftime("%Y", "{col_fecha}") as año FROM "{tabla_name}" WHERE "{col_fecha}" IS NOT NULL ORDER BY año DESC')).fetchall()
    opciones_año = ["Todos"] + [str(a[0]) for a in años_disponibles]
except:
    opciones_año = ["Todos"]

año_seleccionado = st.sidebar.selectbox("Seleccionar Año para Análisis", opciones_año)
filtro_sql = "1=1" if año_seleccionado == "Todos" else f'strftime("%Y", "{col_fecha}") = "{año_seleccionado}"'

st.title(f"🚀 Sistema PNSC")

# SOLUCIÓN AL INDEX ERROR: Añadido "🔎 Buscador" a la lista para habilitar el índice [4]
tabs = st.tabs([
    "📤 Cargar Archivos", 
    "📋 Panel de Control & Estadísticas", 
    "📍 Análisis Geográfico", 
    "🌳 Estructura de Categorías",
    "🔎 Buscador"
])

# --- TAB 1: CARGA Y GESTIÓN ---
with tabs[0]:
    st.subheader("Carga Masiva de Excels")
    archivos_subidos = st.file_uploader("Sube tus archivos .xlsx", type=["xlsx"], accept_multiple_files=True)
    if st.button("Ejecutar Consolidación"):
        if archivos_subidos:
            progreso = st.progress(0)
            fecha_carga = datetime.now().strftime("%d-%m-%Y %H:%M")
            for idx, archivo in enumerate(archivos_subidos):
                df = pd.read_excel(archivo)
                df['archivo_origen'] = archivo.name
                df['fecha_sistema_carga'] = fecha_carga
                if col_fecha in df.columns: df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')
                df.to_sql(tabla_name, engine, if_exists='append', index=False)
                progreso.progress((idx + 1) / len(archivos_subidos))
            st.rerun()

    col_izq, col_der = st.columns(2)
    with col_izq:
        st.divider()
        st.subheader("📂 Historial de Archivos")
        try:
            df_historial = pd.read_sql(f'SELECT archivo_origen as "Archivo", fecha_sistema_carga as "Carga", COUNT(*) as "Registros" FROM "{tabla_name}" GROUP BY Archivo, Carga ORDER BY Carga DESC', engine)
            if not df_historial.empty:
                df_hist_view = df_historial.copy()
                df_hist_view["Registros"] = df_hist_view["Registros"].apply(formato_entero)
                st.dataframe(df_hist_view, use_container_width=True)
                archivo_a_borrar = st.selectbox("Eliminar archivo:", ["---"] + df_historial["Archivo"].unique().tolist())
                if st.button("🗑️ Eliminar"):
                    if archivo_a_borrar != "---":
                        with engine.connect() as conn:
                            conn.execute(text(f'DELETE FROM "{tabla_name}" WHERE archivo_origen = :name'), {"name": archivo_a_borrar})
                            conn.commit()
                        st.rerun()
        except: st.info("Sin registros.")

    with col_der:
        st.divider()
        st.subheader("🗓️ Consolidado por Año")
        try:
            query_años = f'SELECT strftime("%Y", "{col_fecha}") as "Año", COUNT(*) as "Total" FROM "{tabla_name}" GROUP BY 1 ORDER BY 1 DESC'
            df_años = pd.read_sql(query_años, engine)
            if not df_años.empty:
                df_años_view = df_años.copy()
                df_años_view["Total"] = df_años_view["Total"].apply(formato_entero)
                st.dataframe(df_años_view, use_container_width=True)
        except: st.info("Esperando datos...")

# --- TAB 2: PANEL DE CONTROL ---
with tabs[1]:
    st.subheader(f"📊 Estadísticas: {año_seleccionado}")
    if st.button("📊 Calcular Estadísticas"):
        try:
            with engine.connect() as conn:
                res_total = conn.execute(text(f'SELECT COUNT(*) FROM "{tabla_name}" WHERE {filtro_sql}')).scalar()
                res_unicos = conn.execute(text(f'SELECT COUNT(DISTINCT "{columna_id}") FROM "{tabla_name}" WHERE {filtro_sql}')).scalar()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Registros", formato_entero(res_total))
            c2.metric("Cédulas Únicas", formato_entero(res_unicos))
            porc_duplicados = ((res_total - res_unicos) / res_total * 100) if res_total > 0 else 0
            c3.metric("Duplicados", f"{formato_decimal(porc_duplicados)}%")
            
            st.divider()
            query_ente = f'SELECT "{col_ente}" as Institución, COUNT(*) as Total FROM "{tabla_name}" WHERE {filtro_sql} GROUP BY "{col_ente}" ORDER BY Total DESC'
            df_ente = pd.read_sql(query_ente, engine)
            
            if not df_ente.empty:
                chart = alt.Chart(df_ente).mark_bar(color='#29b5e8').encode(
                    x=alt.X('Total:Q', axis=alt.Axis(labelExpr="replace(datum.label, ',', '.')")),
                    y=alt.Y('Institución:N', sort='-x', axis=alt.Axis(labelLimit=1000)),
                    tooltip=[alt.Tooltip('Institución:N'), alt.Tooltip('Total:Q', format=',.0f')]
                ).properties(width=800, height=max(400, len(df_ente) * 20))
                st.altair_chart(chart, use_container_width=True)
                
                df_view = df_ente.copy()
                df_view["Total"] = df_view["Total"].apply(formato_entero)
                st.dataframe(df_view, use_container_width=True)
        except Exception as e: st.error(f"Error: {e}")

# --- TAB 3: ANÁLISIS GEOGRÁFICO ---
with tabs[2]:
    st.subheader(f"📍 Análisis Territorial: {año_seleccionado}")
    if st.button("🔎 Reporte Geográfico"):
        try:
            with engine.connect() as conn:
                n_est = conn.execute(text(f'SELECT COUNT(DISTINCT "{col_estado}") FROM "{tabla_name}" WHERE {filtro_sql}')).scalar()
                n_mun = conn.execute(text(f'SELECT COUNT(DISTINCT "{col_municipio}") FROM "{tabla_name}" WHERE {filtro_sql}')).scalar()
                n_par = conn.execute(text(f'SELECT COUNT(DISTINCT "{col_parroquia}") FROM "{tabla_name}" WHERE {filtro_sql}')).scalar()

            m1, m2, m3 = st.columns(3)
            m1.metric("Estados", formato_entero(n_est))
            m2.metric("Municipios", formato_entero(n_mun))
            m3.metric("Parroquias", formato_entero(n_par))
            
            st.divider()
            query_geo = f'''SELECT "{col_estado}" as Estado, COUNT(*) as Total, COUNT(DISTINCT "{columna_id}") as Unicos 
                            FROM "{tabla_name}" WHERE {filtro_sql} GROUP BY "{col_estado}" ORDER BY Total DESC'''
            df_geo = pd.read_sql(query_geo, engine)
            
            if not df_geo.empty:
                geo_chart = alt.Chart(df_geo).mark_bar(color='#f39c12').encode(
                    x=alt.X('Estado:N', sort='-y'),
                    y=alt.Y('Total:Q', axis=alt.Axis(labelExpr="replace(datum.label, ',', '.')")),
                    tooltip=[alt.Tooltip('Estado'), alt.Tooltip('Total', format=',.0f')]
                ).properties(height=400)
                st.altair_chart(geo_chart, use_container_width=True)
                
                df_geo_view = df_geo.copy()
                df_geo_view["Total"] = df_geo_view["Total"].apply(formato_entero)
                df_geo_view["Unicos"] = df_geo_view["Unicos"].apply(formato_entero)
                st.dataframe(df_geo_view, use_container_width=True)
        except Exception as e: st.error(f"Error: {e}")

# --- TAB 4: CATEGORÍAS ---
with tabs[3]:
    st.subheader(f"🌳 Bloques Unificados ({año_seleccionado})")
    if st.button("🔍 Analizar Jerarquía"):
        try:
            query_cat = f'''SELECT "{col_sub1}" as "N1", "{col_sub2}" as "N2", "{col_sub3}" as "N3", "{col_sub4}" as "N4", COUNT(*) as "Total", COUNT(DISTINCT "{columna_id}") as "Unicos"
                            FROM "{tabla_name}" WHERE {filtro_sql} GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 3, "Total" DESC'''
            df = pd.read_sql(query_cat, engine)
            if not df.empty:
                def generar_html_compacto(df):
                    df['n1_g'] = (df['N1'] != df['N1'].shift()).cumsum()
                    df['n2_g'] = (df['N1'] + df['N2'] != df['N1'].shift() + df['N2'].shift()).cumsum()
                    df['n3_g'] = (df['N1'] + df['N2'] + df['N3'] != df['N1'].shift() + df['N2'].shift() + df['N3'].shift()).cumsum()
                    html = '<div style="max-height: 600px; overflow-y: auto; border: 1px solid #444;">'
                    html += '<table style="width:100%; border-collapse: collapse; color: white; background-color: #0e1117; font-size: 11px;">'
                    html += '<tr style="background-color: #262730; position: sticky; top: 0; z-index: 10;">' + ''.join([f'<th style="padding:4px; border:1px solid #444;">{c}</th>' for c in [col_sub1, col_sub2, col_sub3, col_sub4, "Total", "Únicos"]]) + '</tr>'
                    for i in range(len(df)):
                        html += '<tr>'
                        for col, grp_col in [('N1', 'n1_g'), ('N2', 'n2_g'), ('N3', 'n3_g')]:
                            if i == 0 or df.iloc[i][grp_col] != df.iloc[i-1][grp_col]:
                                rowspan = len(df[df[grp_col] == df.iloc[i][grp_col]])
                                html += f'<td rowspan="{rowspan}" style="padding:4px; border:1px solid #444; vertical-align: middle; background-color:#1a1c24; font-weight:bold;">{df.iloc[i][col]}</td>'
                        html += f'<td style="padding:4px; border:1px solid #444;">{df.iloc[i]["N4"]}</td>'
                        html += f'<td style="padding:4px; border:1px solid #444; text-align:center;">{formato_entero(df.iloc[i]["Total"])}</td>'
                        html += f'<td style="padding:4px; border:1px solid #444; text-align:center;">{formato_entero(df.iloc[i]["Unicos"])}</td></tr>'
                    return html + '</table></div>'
                st.markdown(generar_html_compacto(df), unsafe_allow_html=True)
        except Exception as e: st.error(f"Error: {e}")

# --- TAB 5: BUSCADOR (ARCHIVO EXTERNO) ---
with tabs[4]:
    # Llama a la función del archivo externo pasando las variables necesarias
    pb.renderizar_nueva_pestaña(engine, tabla_name, formato_entero)