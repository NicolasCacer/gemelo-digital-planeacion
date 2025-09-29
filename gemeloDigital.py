import streamlit as st
import pandas as pd
import numpy as np
import time
from demanda import generar_pronostico_demanda
from agregacion import planeacion_agregada
from desagregacion import desagregar_produccion
from simulacion import simular_flowshop

def dashboard_streamlit():
    st.set_page_config(page_title="Gemelo Digital - Planta de Bebidas", layout="wide")
    st.title("Gemelo Digital - Planta de Bebid")

    # ---------- Sidebar: Parámetros ----------
    st.sidebar.header("Parámetros de simulación")

    # Demanda
    demanda_pred = st.sidebar.slider("Demanda mensual por unidad", 50, 200, 100)

    # Costos
    costo_produccion = st.sidebar.number_input("Costo producción por unidad", 1, 50, 10)
    costo_inventario = st.sidebar.number_input("Costo inventario por unidad", 0, 20, 2)

    # Días por mes
    dias_por_mes = st.sidebar.number_input("Días por mes", 28, 31, 30)

    # Tiempos de proceso
    tiempo_mezcla = st.sidebar.slider("Tiempo mezcla (min)", 15, 25, 20)
    tiempo_pasteurizacion = st.sidebar.slider("Tiempo pasteurización (min)", 30, 45, 35)
    tiempo_llenado = st.sidebar.slider("Tiempo llenado (min)", 10, 15, 12)
    tiempo_etiquetado = st.sidebar.slider("Tiempo etiquetado (min)", 15, 25, 20)
    tiempo_almacenamiento = st.sidebar.slider("Tiempo almacenamiento (h)", 0, 48, 24)

    # ---------- Generar pronóstico ----------
    meses = [f'Mes {i+1}' for i in range(12)]
    demanda_df = generar_pronostico_demanda(meses, demanda_pred)

    st.subheader("Pronóstico de Demanda")
    st.dataframe(demanda_df)

    # ---------- Planeación agregada ----------
    demanda_df = planeacion_agregada(demanda_df, costo_produccion, costo_inventario)
    st.subheader("Planeación Agregada")
    st.dataframe(demanda_df)

    # ---------- Desagregación diaria ----------
    demanda_df = desagregar_produccion(demanda_df, dias_por_mes)
    st.subheader("Producción Diaria Estimada")
    st.dataframe(demanda_df[['Mes','Produccion_diaria']])

    # ---------- Visualización de producción ----------
    st.subheader("Gráficos de Producción")
    col1, col2 = st.columns(2)
    with col1:
        st.write("Producción mensual planificada")
        st.bar_chart(demanda_df.set_index('Mes')['Produccion_planificada'])
    with col2:
        st.write("Producción diaria promedio")
        st.line_chart(demanda_df.set_index('Mes')['Produccion_diaria'])

    # ---------- Simulación animada ----------
    st.subheader("Simulación Flowshop (Animada)")
    placeholder = st.empty()

    # Ejecutar simulación con animación
    for i in range(1, len(demanda_df)+1):
        sub_df = demanda_df.head(i)
        placeholder.bar_chart(sub_df.set_index('Mes')['Produccion_planificada'])
        time.sleep(0.5)  # pausa corta para simular animación

    # Simulación completa
    WIP_log = simular_flowshop(
        produccion_diaria=demanda_df,
        tiempo_mezcla=tiempo_mezcla,
        tiempo_pasteurizacion=tiempo_pasteurizacion,
        tiempo_llenado=tiempo_llenado,
        tiempo_etiquetado=tiempo_etiquetado,
        tiempo_almacenamiento=tiempo_almacenamiento
    )

    # ---------- KPIs ----------
    st.subheader("KPIs de la Simulación")
    WIP_total = np.mean(WIP_log)
    Throughput_total = sum(demanda_df['Produccion_planificada'])
    Cycle_time_prom = np.mean(WIP_log)

    st.write(f"WIP promedio (minutos): {WIP_total:.2f}")
    st.write(f"Throughput total: {Throughput_total}")
    st.write(f"Cycle time promedio por lote (minutos): {Cycle_time_prom:.2f}")
    st.success("Simulación completada!")

# Ejecutar dashboard
if __name__ == "__main__":
    dashboard_streamlit()
