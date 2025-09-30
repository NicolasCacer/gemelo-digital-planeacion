import streamlit as st
import pandas as pd
from demanda import generar_pronostico_demanda
from agregacion import planeacion_agregada_completa
from desagregacion import desagregar_produccion
from simulacion import simular_flowshop_dashboard

def dashboard_streamlit():
    st.set_page_config(page_title="Gemelo Digital - Demanda y Agregación", layout="wide")
    st.title("Gemelo Digital - Demanda y Plan Agregado")

    # ---------- 1️⃣ Demanda editable ----------
    df_demanda = generar_pronostico_demanda()
    df_demanda = df_demanda.rename(columns={'mes': 'Mes', 'bebida': 'Producto', 'demanda_esperada': 'Demanda'})
    st.subheader("Demanda mensual por producto (editable)")
    edited_demanda = st.data_editor(df_demanda, num_rows="dynamic", use_container_width=True)

    # ---------- 2️⃣ Costos de agregación editable ----------
    st.subheader("Coeficientes de recursos por categoría y producto")
    categorias = ['Horas Hombre', 'Materia prima']
    productos = edited_demanda['Producto'].unique()
    meses = [f'Mes {i}' for i in range(1,13)]
    costos_rows = []

    costos_default = {
        'Horas Hombre': {p: 10 for p in productos},
        'Materia prima': {p: 15 for p in productos}
    }

    for cat in categorias:
        for prod in productos:
            row = {'Categoría': cat, 'Producto': prod}
            for mes in meses:
                row[mes] = costos_default.get(cat, {}).get(prod, 0)
            costos_rows.append(row)

    df_costos = pd.DataFrame(costos_rows)
    edited_costos = st.data_editor(df_costos, num_rows="dynamic", use_container_width=True)

    # ---------- 3️⃣ Selección de categoría para agregación ----------
    categoria_sel = st.selectbox("Seleccione categoría para agregación", categorias)

    # ---------- 4️⃣ Ejecutar planeación agregada ----------
    if st.button("Generar Plan Agregado"):
        df_plan = planeacion_agregada_completa(
            demanda_df=edited_demanda,
            costos_df=edited_costos,
            categoria_agregar=categoria_sel
        )
        st.subheader(f"Plan Agregado ({categoria_sel})")
        st.dataframe(df_plan)

        # 2️⃣ Desagregar producción directamente desde df_plan
        # ---------- 5️⃣ Desagregar producción directamente desde df_plan ----------
        df_desagregado = desagregar_produccion(df_plan)
        st.subheader(f"Producción Desagregada ({categoria_sel})")
        st.dataframe(df_desagregado)
        # Dentro del dashboard después de desagregar la producción
        # df_WIP = simular_flowshop_dashboard(df_desagregado,
        #                                     tiempo_mezcla=60,
        #                                     tiempo_pasteurizacion=120,
        #                                     tiempo_llenado=30,
        #                                     tiempo_etiquetado=20,
        #                                     tiempo_almacenamiento=24)

        # st.subheader("Simulación Flowshop")
        # st.dataframe(df_WIP)



# ---------- Ejecución ----------
if __name__ == "__main__":
    dashboard_streamlit()
