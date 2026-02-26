import streamlit as st
import pandas as pd
import unicodedata

def normalizar_texto(texto):
    """Elimina acentos y convierte a minúsculas para una búsqueda exacta."""
    if not texto: return ""
    texto = str(texto).lower()
    # Eliminar acentos
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')
    return texto

def renderizar_nueva_pestaña(engine, tabla_name, formato_entero):
    st.subheader("🔭 Resumen por Áreas Temáticas (Normalizado)")
    st.info("Este análisis agrupa las categorías ignorando mayúsculas, minúsculas y acentos.")

    try:
        query = f'SELECT * FROM "{tabla_name}"'
        df = pd.read_sql(query, engine)

        if df.empty:
            st.warning("No hay datos disponibles.")
            return

        # Definición de áreas y sus palabras clave (sin acentos para la comparación)
        mapeo_areas = {
            "Robótica": ["robotica", "robot", "meca"],
            "Astronomía": ["astronomia", "espacio", "astros", "planeta"],
            "Ciencia para la Producción": ["produccion", "agro", "industria", "fabrica"],
            "Ciencia para la Computación": ["computacion", "programacion", "software", "informatica"],
            "Biología y Salud": ["biologia", "salud", "medicina", "celulas"],
            "Química": ["quimica", "laboratorio", "molecula"],
            "Física": ["fisica", "energia", "cuantica"],
            "Matemáticas": ["matematica", "calculo", "algebra"],
            "Ciencias Sociales": ["sociales", "comunidad", "humanidades"],
            "Ecología y Ambiente": ["ambiente", "ecologia", "clima", "reciclaje"],
            "Electrónica": ["electronica", "circuitos", "sensores"],
            "Telecomunicaciones": ["telecomunicaciones", "redes", "satelite"],
            "Biotecnología": ["biotecnologia", "genetica", "adn"],
            "Innovación y Emprendimiento": ["innovacion", "emprendimiento", "startup"],
            "Ingeniería": ["ingenieria", "diseño", "prototipo"]
        }

        # Función de búsqueda inteligente
        def asignar_area(row):
            # Combinamos los 4 niveles y normalizamos el texto (sin acentos, minúsculas)
            texto_unido = f"{row.get('SubCatg1', '')} {row.get('SubCatg2', '')} {row.get('SubCatg3', '')} {row.get('SubCatg4', '')}"
            texto_limpio = normalizar_texto(texto_unido)
            
            for area, keywords in mapeo_areas.items():
                for word in keywords:
                    if word in texto_limpio:
                        return area
            return "Otras Áreas"

        # Aplicamos la lógica
        df['Area_Agrupada'] = df.apply(asignar_area, axis=1)

        # Agrupamos y ordenamos
        resumen = df.groupby('Area_Agrupada').size().reset_index(name='Cantidad')
        resumen = resumen.sort_values(by='Cantidad', ascending=False).head(15)

        # --- Visualización ---
        st.write("### 📊 Participantes por Área")
        cols = st.columns(3)
        for i, (index, row) in enumerate(resumen.iterrows()):
            with cols[i % 3]:
                st.metric(label=row['Area_Agrupada'], value=formato_entero(row['Cantidad']))

        st.divider()
        st.write("### 📋 Resumen de Grupos")
        
        # Formato de frase solicitado
        resumen['Descripción'] = resumen['Area_Agrupada'].apply(lambda x: f"Jóvenes participantes en el área de {x}")
        resumen_vista = resumen[['Descripción', 'Cantidad']].copy()
        resumen_vista['Cantidad'] = resumen_vista['Cantidad'].apply(formato_entero)
        
        st.table(resumen_vista)

    except Exception as e:
        st.error(f"Error en el procesamiento de datos: {e}")
