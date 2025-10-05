import streamlit as st
import pandas as pd
from demanda import generar_demanda_sarima, graficar_demanda_interactivo
from agregacion import planeacion_agregada_completa
from demanda import inventario_inicial
from desagregacion import desagregar_produccion, grafica_consolidada
from simulacion import simular_produccion  # Función encapsulada de SimPy

def dashboard_streamlit():
    st.set_page_config(
        page_title="Gemelo Digital - Demanda y Producción",
        layout="wide"
    )

    st.title("🚀 Gemelo Digital - Planificación de Producción y Demanda")
    st.markdown(
        "Este dashboard permite proyectar la demanda, planificar la producción agregada y desagregada, "
        "y simular la operación de producción para analizar métricas clave como WIP, ciclo de lote, throughput y utilización de recursos."
    )

    # Sidebar
    st.sidebar.header("Parámetros Generales")
    num_per = st.sidebar.number_input("Número de períodos a proyectar", min_value=1, max_value=36, value=12, step=1)

    st.sidebar.header("Parámetros de Simulación de Producción")
    num_lotes = st.sidebar.slider("Número de lotes", 1, 50, 10)
    tamano_lote = st.sidebar.slider("Tamaño de lote (botellas)", 50, 500, 100)
    num_mezcla = st.sidebar.slider("Equipos de mezcla", 1, 5, 2)
    num_pasteurizacion = st.sidebar.slider("Equipos de pasteurización", 1, 5, 2)
    num_llenado = st.sidebar.slider("Líneas de llenado", 1, 5, 2)
    num_etiquetado = st.sidebar.slider("Estaciones de etiquetado", 1, 5, 2)
    num_camaras = st.sidebar.slider("Cámaras de refrigeración", 1, 5, 1)

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Demanda",
        "📈 Planeación Agregada",
        "📉 Planeación Desagregada",
        "⚙️ Simulación de Producción"
    ])

    # Tab 1: Demanda
    with tab1:
        st.subheader("Demanda proyectada por producto")
        df_demanda = generar_demanda_sarima(n_periodos=num_per)
        st.markdown("Edite los valores de demanda si desea ajustar la proyección antes de la planeación.")
        edited_demanda = st.data_editor(df_demanda.copy(), num_rows="dynamic", width='stretch')

        fecha_max_hist = st.date_input("Seleccione la fecha máxima histórica:", value=pd.Timestamp('2024-01-01'))
        fecha_max_hist = pd.Timestamp(fecha_max_hist)
        if 'fecha' in edited_demanda.columns:
            edited_demanda['fecha'] = pd.to_datetime(edited_demanda['fecha'], errors='coerce')

        fig_demanda = graficar_demanda_interactivo(df_demanda_esperada=edited_demanda, fecha_max_hist=fecha_max_hist)
        st.plotly_chart(fig_demanda, use_container_width=True)
        st.markdown("💡 *Este gráfico muestra la proyección de demanda por producto. Puede comparar la demanda histórica con la proyectada y ajustar manualmente los valores si es necesario.*")

    # Tab 2: Planeación Agregada
    with tab2:
        st.subheader("Planeación Agregada")
        st.markdown("Esta sección muestra la planeación agregada mensual basada en la demanda proyectada. Permite analizar la producción total requerida por período.")
        df_plan_agg, fig_df_plan_agg = planeacion_agregada_completa(
            demanda_df=edited_demanda,
            inv_in_df=inventario_inicial(),
            num_per=num_per
        )
        st.dataframe(df_plan_agg.reset_index(drop=True), use_container_width=True)
        st.plotly_chart(fig_df_plan_agg, use_container_width=True)

    # Tab 3: Planeación Desagregada
    with tab3:
        st.subheader("Producción Desagregada por Producto")
        st.markdown("Esta planeación distribuye la producción agregada entre los diferentes productos, permitiendo visualizar inventarios finales y producción asignada por producto y período.")
        df_prod, df_inv_desagg, df_resultado, fig_desagg = desagregar_produccion(
            demanda_df=edited_demanda,
            df_inventario_inicial=inventario_inicial(),
            resultados=df_plan_agg,
            num_per=num_per
        )
        st.dataframe(df_prod.reset_index(drop=True), use_container_width=True)
        st.subheader("Inventario desagregado")
        st.dataframe(df_inv_desagg.reset_index(drop=True), use_container_width=True)
        st.plotly_chart(fig_desagg, use_container_width=True)

        st.subheader("Gráfico consolidado de producción e inventario")
        fig_cons = grafica_consolidada(df_prod, df_inv_desagg, df_resultado, productos=edited_demanda['bebida'].unique().tolist())
        st.plotly_chart(fig_cons, use_container_width=True)

    # Tab 4: Simulación de Producción
    with tab4:
        st.subheader("Simulación de Producción (SimPy)")
        st.markdown("Ejecute la simulación para analizar métricas clave del sistema de producción, incluyendo WIP, tiempo de ciclo, throughput y utilización de recursos.")

        with st.expander("Configuración de simulación"):
            st.write("Ajuste los parámetros del sistema de producción antes de ejecutar la simulación:")
            st.markdown(f"- Número de lotes: **{num_lotes}**")
            st.markdown(f"- Tamaño de lote: **{tamano_lote} botellas**")
            st.markdown(f"- Equipos de mezcla: **{num_mezcla}**")
            st.markdown(f"- Equipos de pasteurización: **{num_pasteurizacion}**")
            st.markdown(f"- Líneas de llenado: **{num_llenado}**")
            st.markdown(f"- Estaciones de etiquetado: **{num_etiquetado}**")
            st.markdown(f"- Cámaras de refrigeración: **{num_camaras}**")

        if st.button("Ejecutar simulación"):
            df_sim_resultados, df_sim_utilizacion, df_sim_metricas = simular_produccion(
                num_lotes=num_lotes,
                tamano_lote_max=tamano_lote,
                num_mezcla=num_mezcla,
                num_pasteurizacion=num_pasteurizacion,
                num_llenado=num_llenado,
                num_etiquetado=num_etiquetado,
                num_camaras=num_camaras
            )

            st.markdown("### Resultados de los lotes")
            st.dataframe(df_sim_resultados.reset_index(drop=True), use_container_width=True)

            st.markdown("### Utilización de recursos")
            st.dataframe(df_sim_utilizacion.reset_index(drop=True), use_container_width=True)

            st.markdown("### Métricas globales de producción")
            st.dataframe(df_sim_metricas.reset_index(drop=True), use_container_width=True)

    st.markdown("---")
    st.markdown("💡 *Este dashboard permite analizar la planificación de producción y la simulación de manera integral. Use los controles en la barra lateral para ajustar parámetros y observe cómo impactan las métricas de desempeño.*")
