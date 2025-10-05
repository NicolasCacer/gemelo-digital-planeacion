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
    num_per = st.sidebar.slider("Número de períodos a proyectar", min_value=1, max_value=48, value=12, step=1)
    tamano_lote = st.sidebar.slider("Tamaño de lote (unidades):", min_value=1, max_value=1000, value=100, step=10)
    litros_por_unidad = st.sidebar.slider("litros por unidad", min_value=0.1, max_value=3.5, value=0.5, step=0.1)
    
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

        # --- Guardar el orden original ---
        df_demanda['orden_original'] = range(len(df_demanda))

        # --- Ordenar temporalmente para mostrar últimos registros primero ---
        df_demanda_sorted = df_demanda.sort_values(['anio','mes','bebida'], ascending=False)

        # --- Seleccionar solo columnas visibles para el editor ---
        visible_cols = [c for c in df_demanda_sorted.columns if c != 'orden_original']

        # --- Data editor ---
        edited_demanda = st.data_editor(
            df_demanda_sorted[visible_cols].copy(),
            num_rows="dynamic",
            width='stretch'
        )

        # --- Recuperar el orden original ---
        edited_demanda = edited_demanda.assign(
            orden_original=df_demanda_sorted['orden_original']
        ).sort_values('orden_original').drop(columns='orden_original')

        # --- Convertir fecha ---
        # Última fecha histórica oficial del DANE
        fecha_max_hist = pd.Timestamp('2023-12-31')

        st.markdown(
            f"""
            <div style='
                background-color:#E0F7FA;
                padding:10px;
                border-radius:10px;
                border: 1px solid #00ACC1;
                width: fit-content;
                display: inline-block;
                font-size:16px;
                font-weight:bold;
            '>
                📅 Último dato histórico oficial del DANE: {fecha_max_hist.strftime('%d/%m/%Y')}
            </div>
            """, unsafe_allow_html=True
        )


        # --- Gráfico ---
        
        st.markdown("💡 *Este gráfico muestra la proyección de demanda por producto. Puede comparar la demanda histórica con la proyectada y ajustar manualmente los valores si es necesario.*")
        fig_demanda = graficar_demanda_interactivo(df_demanda_esperada=edited_demanda)
        st.plotly_chart(fig_demanda, config={"responsive": True}, use_container_width=True)


    # Tab 2: Planeación Agregada
    with tab2:
        st.subheader("Planeación Agregada")
        st.markdown(
            "Esta sección muestra la planeación agregada mensual basada en la demanda proyectada. "
            "Permite analizar la producción total requerida por período y ajustar los parámetros de costos y capacidad."
        )

        # =============================
        # Inputs de usuario para parámetros
        # =============================
        st.markdown("### Ajuste de parámetros")

        with st.expander("Ajuste de parámetros", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                Ct = st.number_input("Costo producción (Ct)", value=10.0, step=1.0)
                Ht = st.number_input("Costo inventario (Ht)", value=10.0, step=1.0)
                CRt = st.number_input("Costo fuerza laboral regular (CRt)", value=10.0, step=1.0)
                COt = st.number_input("Costo horas extras (COt)", value=10.0, step=1.0)
            with col2:
                PIt = st.number_input("Costo backlog (PIt)", value=1e10, step=1e9, format="%.0f")
                CW_mas = st.number_input("Costo contratación (CW_mas)", value=100.0, step=1.0)
                CW_menos = st.number_input("Costo despidos (CW_menos)", value=200.0, step=1.0)
            with col3:
                M = st.number_input("Horas por unidad (M)", value=1.0, step=0.1)
                LR_inicial = st.number_input("Fuerza laboral inicial (LR_inicial)", value=10*160, step=10)
                inv_seg = st.number_input("Inventario mínimo relativo (inv_seg)", value=0.0, step=0.01)

        # =============================
        # Llamada a la función con parámetros ajustables
        # =============================
        df_plan_agg, fig_df_plan_agg = planeacion_agregada_completa(
            demanda_df=edited_demanda,
            inv_in_df=inventario_inicial(),
            num_per=num_per,
            Ct=Ct,
            Ht=Ht,
            CRt=CRt,
            COt=COt,
            PIt=PIt,
            CW_mas=CW_mas,
            CW_menos=CW_menos,
            M=M,
            LR_inicial=LR_inicial,
            inv_seg=inv_seg
        )
        st.plotly_chart(fig_df_plan_agg, config={"responsive": True}, use_container_width=True)
        st.dataframe(df_plan_agg.reset_index(drop=True), width='stretch')

    # Tab 3: Planeación Desagregada
    with tab3:
        st.subheader("Producción Desagregada por Producto")
        with st.expander("Ajuste de parámetros de desagregación", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                cost_prod_ = st.number_input(
                    "Costo producción (Ct)",
                    min_value=1.0,
                    value=1.0,
                    step=1.0,
                    key="cost_prod_tab3"
                )
            with col2:
                cost_inv_ = st.number_input(
                    "Costo inventario (Ht)",
                    min_value=1.0,
                    value=1.0,
                    step=1.0,
                    key="cost_inv_tab3"
                )


        st.markdown("Esta planeación distribuye la producción agregada entre los diferentes productos, permitiendo visualizar inventarios finales y producción asignada por producto y período.")
        df_prod, df_inv_desagg, df_resultado, fig_desagg = desagregar_produccion(
            demanda_df=edited_demanda,
            df_inventario_inicial=inventario_inicial(),
            resultados=df_plan_agg,
            num_per=num_per,
            cost_prod=cost_prod_,
            cost_inv=cost_inv_
        )
        st.plotly_chart(fig_desagg, config={"responsive": True}, use_container_width=True)
        
        st.subheader("Producción desagregada")
        st.dataframe(df_prod.reset_index(drop=True), width='stretch')
        
        st.subheader("Inventario desagregado")
        st.dataframe(df_inv_desagg.reset_index(drop=True), width='stretch')

    # Tab 4: Simulación de Producción
    with tab4:
        st.subheader("Gráfico consolidado de producción e inventario")
        fig_cons = grafica_consolidada(
            df_prod, df_inv_desagg, df_resultado,
            productos=edited_demanda['bebida'].unique().tolist(),
            lote=tamano_lote,
            litros_por_unidad=litros_por_unidad
        )
        st.plotly_chart(fig_cons, config={"responsive": True}, use_container_width=True)
        
        st.subheader("Simulación de Producción")
        st.markdown(
            "Ejecute la simulación para analizar métricas clave del sistema de producción, "
            "incluyendo WIP, tiempo de ciclo, throughput y utilización de recursos."
        )

        with st.expander("⚙️ Configuración de simulación", expanded=True):
            num_mezcla = st.slider("Equipos de mezcla:", min_value=1, max_value=10, value=1, step=1)
            num_pasteurizacion = st.slider("Equipos de pasteurización:", min_value=1, max_value=10, value=1, step=1)
            num_llenado = st.slider("Líneas de llenado:", min_value=1, max_value=10, value=1, step=1)
            num_etiquetado = st.slider("Estaciones de etiquetado:", min_value=1, max_value=10, value=1, step=1)
            num_camaras = st.slider("Cámaras de refrigeración:", min_value=1, max_value=10, value=1, step=1)

        if st.button("🚀 Ejecutar simulación"):
            with st.spinner("Simulando producción según el plan desagregado..."):
                df_sim_resultados, df_sim_utilizacion, df_sim_metricas = simular_produccion(
                    df_desagregacion=df_prod,   # conexión directa con la desagregación
                    tamano_lote_max=tamano_lote,
                    num_mezcla=num_mezcla,
                    num_pasteurizacion=num_pasteurizacion,
                    num_llenado=num_llenado,
                    num_etiquetado=num_etiquetado,
                    num_camaras=num_camaras
                )


            st.success("✅ Simulación completada")

            # --- Mostrar resultados clave ---
            st.markdown("### 📊 Métricas globales de producción")

            # Mostrar KPIs de manera visual
            if not df_sim_metricas.empty:
                wip = df_sim_metricas.loc[0, "WIP"]
                cycle_time = df_sim_metricas.loc[0, "Cycle_time"]
                throughput = df_sim_metricas.loc[0, "Throughput"]
                takt_time = df_sim_metricas.loc[0, "Takt_time"]

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric(
                        label="🧱 WIP (Work in Process)",
                        value=f"{wip:.2f}",
                        help="Cantidad promedio de lotes en proceso simultáneamente."
                    )
                with col2:
                    st.metric(
                        label="⏱️ Cycle Time (min)",
                        value=f"{cycle_time:.1f}",
                        help="Tiempo promedio que tarda un lote en completarse."
                    )
                with col3:
                    st.metric(
                        label="⚡ Throughput (lotes/min)",
                        value=f"{throughput:.3f}",
                        help="Cantidad promedio de lotes completados por minuto."
                    )
                with col4:
                    st.metric(
                        label="📏 Takt Time (min/lote)",
                        value=f"{takt_time:.1f}",
                        help="Tiempo promedio entre la finalización de lotes sucesivos."
                    )
            else:
                st.warning("No se generaron métricas en esta simulación.")


            st.markdown("### ⚙️ Utilización de recursos")
            st.dataframe(df_sim_utilizacion.reset_index(drop=True), width='stretch')

            # --- Mostrar detalles solo si el usuario quiere ---
            with st.expander("📦 Ver detalle de lotes (opcional)"):
                st.markdown("El siguiente DataFrame muestra cada lote procesado con sus tiempos y estado final.")
                st.dataframe(df_sim_resultados.reset_index(drop=True).head(200), width='stretch')
                st.caption("💡 Solo se muestran los primeros 200 registros para evitar sobrecarga de memoria.")

                # Permitir descarga completa
                csv = df_sim_resultados.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇️ Descargar resultados completos (CSV)",
                    data=csv,
                    file_name="resultados_simulacion.csv",
                    mime="text/csv"
                )

    # --- Footer ---
    st.markdown("---")
    st.markdown(
        "💡 *Este dashboard permite analizar la planificación de producción y la simulación de manera integral. "
        "Use los controles en la barra lateral para ajustar parámetros y observe cómo impactan las métricas de desempeño.*"
    )