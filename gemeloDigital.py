import streamlit as st
import pandas as pd
from demanda import generar_demanda_sarima, graficar_demanda_interactivo
from agregacion import planeacion_agregada_completa
from demanda import inventario_inicial

def dashboard_streamlit():
    st.set_page_config(page_title="Gemelo Digital - Demanda y Agregación", layout="wide")
    st.title("Gemelo Digital - Demanda y Plan Agregado")
    num_per = st.number_input(
        "Número de períodos a proyectar",
        min_value=1,
        max_value=36,
        value=12,  # valor por defecto
        step=1
    )
    # ---------- Demanda editable ----------
    df_demanda = generar_demanda_sarima(n_periodos=num_per)
    st.subheader("Demanda (Litros) mensual por producto")
    edited_demanda = st.data_editor(df_demanda, num_rows="dynamic", width='stretch')
    
    fecha_max_hist = st.date_input(
        "Seleccione la fecha máxima histórica:",
        value=pd.Timestamp('2024-01-01')  # valor por defecto
    )

    # Convertir a Timestamp si no lo está
    fecha_max_hist = pd.Timestamp(fecha_max_hist)

    # ---------- Graficar demanda ----------
    fig = graficar_demanda_interactivo(df_demanda_esperada=edited_demanda, fecha_max_hist=fecha_max_hist)
    st.plotly_chart(fig, use_container_width=True)
        
    df_plan_agg, fig_df_plan_agg = planeacion_agregada_completa(demanda_df = edited_demanda,inv_in_df = inventario_inicial(), num_per=num_per)
    st.subheader("Planeación agregada")
    st.dataframe(df_plan_agg)  # Ajusta tamaño
    st.plotly_chart(fig_df_plan_agg, use_container_width=True)




# ---------- Ejecución ----------
if __name__ == "__main__":
    dashboard_streamlit()
