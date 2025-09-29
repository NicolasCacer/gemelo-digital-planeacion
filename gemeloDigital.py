# dashboard.py

import streamlit as st
import numpy as np
from demanda import generar_pronostico_demanda
from agregacion import planeacion_agregada
from desagregacion import desagregar_produccion
from simulacion import simular_flowshop

def dashboard_streamlit():
    st.set_page_config(page_title="Gemelo Digital - Planta de Bebidas", layout="wide")
    st.title("Gemelo Digital - Planta de Bebidas")

    # Meses
    meses = [f'Mes {i+1}' for i in range(12)]

    # --- Pronóstico de demanda ---
    demanda_pred = st.slider("Demanda mensual por unidad", 50, 200, 100)
    demanda_df = generar_pronostico_demanda(meses, demanda_pred)
    st.subheader("Pronóstico de Demanda")
    st.dataframe(demanda_df)

    # --- Planeación agregada ---
    costo_produccion = st.number_input("Costo producción por unidad", 1, 50, 10)
    costo_inventario = st.number_input("Costo inventario por unidad", 0, 20, 2)
    demanda_df = planeacion_agregada(demanda_df, costo_produccion, costo_inventario)
    st.subheader("Planeación Agregada")
    st.dataframe(demanda_df)

    # --- Desagregación diaria ---
    dias_por_mes = st.number_input("Días por mes", 28, 31, 30)
    demanda_df = desagregar_produccion(demanda_df, dias_por_mes)
    st.subheader("Producción Diaria Estimada")
    st.dataframe(demanda_df[['Mes','Produccion_diaria']])

    # --- Parámetros de simulación ---
    tiempo_mezcla = st.slider("Tiempo mezcla (min)", 15, 25, 20)
    tiempo_pasteurizacion = st.slider("Tiempo pasteurización (min)", 30, 45, 35)
    tiempo_llenado = st.slider("Tiempo llenado (min)", 10, 15, 12)
    tiempo_etiquetado = st.slider("Tiempo etiquetado (min)", 15, 25, 20)
    tiempo_almacenamiento = st.slider("Tiempo almacenamiento (h)", 0, 48, 24)

    # --- Simulación ---
    WIP_log = simular_flowshop(
        produccion_diaria=demanda_df,
        tiempo_mezcla=tiempo_mezcla,
        tiempo_pasteurizacion=tiempo_pasteurizacion,
        tiempo_llenado=tiempo_llenado,
        tiempo_etiquetado=tiempo_etiquetado,
        tiempo_almacenamiento=tiempo_almacenamiento
    )

    # --- KPIs ---
    st.subheader("KPIs Simulación")
    WIP_total = np.mean(WIP_log)
    Throughput_total = sum(demanda_df['Produccion_planificada'])
    Cycle_time_prom = np.mean(WIP_log)

    st.write(f"WIP promedio (minutos): {WIP_total:.2f}")
    st.write(f"Throughput total: {Throughput_total}")
    st.write(f"Cycle time promedio por lote (minutos): {Cycle_time_prom:.2f}")
    st.success("Simulación completada!")

# Solo se ejecuta si este archivo se corre directamente
if __name__ == "__main__":
    dashboard_streamlit()
