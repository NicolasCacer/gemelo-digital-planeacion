import streamlit as st
import scipy.stats as stt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
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
    with st.sidebar:
        st.markdown("## ⚙️ **Parámetros Generales**")
        st.markdown(
            """
            Ajusta los parámetros básicos para la simulación y proyección de producción.
            Estos valores afectan el volumen total estimado y los resultados visuales.
            
            """
        )

        num_per = st.slider(
            "📆 Número de meses a proyectar",
            min_value=1, max_value=48, value=1, step=1,
            help="Define cuántos meses o períodos quieres simular hacia adelante."
        )

        tamano_lote = st.slider(
            "📦 Tamaño máximo de lote (unidades)",
            min_value=100, max_value=1000, value=100, step=50,
            help="Cantidad máxima de unidades por lote de producción."
        )

        litros_por_unidad = st.slider(
            "💧 Litros de producto por unidad",
            min_value=0.1, max_value=3.5, value=0.5, step=0.1,
            help="Volumen promedio (en litros) de cada unidad producida."
        )
        
        porc_part = st.slider(
            "💸 Participación de mercado (%)",
            min_value=0.005,
            max_value=0.5,
            value=0.01,
            step=0.01,
            help="Define el porcentaje de participación de mercado para este producto (1% - 50%)."
        )

    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Demanda",
        "📈 Planeación Agregada",
        "📉 Planeación Desagregada",
        "⚙️ Simulación de Producción"
    ])

    # Tab 1: Demanda
    with tab1:
        st.subheader("Demanda proyectada por producto")
        st.markdown("Edite los valores de demanda si desea ajustar la proyección antes de la planeación.")
        
        df_demanda = generar_demanda_sarima(n_periodos=num_per, porc_part=porc_part)

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
            <style>
            .info-box {{
                background-color: #E0F7FA;
                padding: 10px 18px;
                border-radius: 10px;
                border: 1px solid #00ACC1;
                width: fit-content;
                display: inline-block;
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 25px;
                color: #000000; /* color por defecto para modo claro */
                transition: all 0.3s ease;
            }}

            /* Ajuste para modo oscuro */
            @media (prefers-color-scheme: dark) {{
                .info-box {{
                    background-color: #004D40;
                    border: 1px solid #26A69A;
                    color: #FFFFFF; /* texto blanco en modo oscuro */
                }}
            }}
            </style>

            <div class="info-box">
                📅 Último dato histórico oficial del DANE: {fecha_max_hist.strftime('%d/%m/%Y')}
            </div>
            """,
            unsafe_allow_html=True
        )



        # --- Gráfico ---
        
        st.markdown("💡 *Este gráfico muestra la proyección de demanda por producto. Puede comparar la demanda histórica con la proyectada y ajustar manualmente los valores si es necesario.*")
        fig_demanda = graficar_demanda_interactivo(df_demanda_esperada=edited_demanda)
        st.plotly_chart(fig_demanda, config={"responsive": True}, use_container_width=True)


    # =============================
    # TAB 2: Planeación Agregada
    # =============================
    with tab2:
        st.subheader("Planeación Agregada")
        st.markdown(
            "Esta sección muestra la **planeación agregada mensual** basada en la demanda proyectada. "
            "Permite ajustar los parámetros de **costos, capacidad y fuerza laboral**, para evaluar escenarios de producción."
        )

        st.markdown("### ⚙️ Ajuste de parámetros del modelo")

        with st.expander("🔧 Configuración general del modelo", expanded=True):
            st.markdown("Ajusta los **parámetros económicos, laborales y técnicos** que impactan la simulación de planeación.")

            # =========================
            # 💰 COSTOS OPERATIVOS
            # =========================
            st.markdown("#### 💰 Costos operativos")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                Ct = st.number_input("Costo de producción (Ct)", value=10.0, step=1.0,
                    help="Costo directo asociado a producir una unidad.")
            with col2:
                Ht = st.number_input("Costo de inventario (Ht)", value=10.0, step=1.0,
                    help="Costo por mantener inventario en bodega durante un período.")
            with col3:
                PIt = st.number_input("Costo de backlog (PIt)", value=1e10, step=1e9, format='%.0f',
                    help="Penalización por no cumplir con la demanda a tiempo.")
            with col4:
                inv_seg = st.number_input("Inventario mínimo relativo (inv_seg)", value=0.0, step=0.01,
                    help="Proporción mínima del inventario objetivo que debe mantenerse.")

            st.divider()

            # =========================
            # 👷 FUERZA LABORAL
            # =========================
            st.markdown("#### 👷 Fuerza laboral y capacidad operativa")
            st.caption("Define los costos y la estructura de turnos del personal productivo.")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                CRt = st.number_input("Costo laboral regular (CRt)", value=10.0, step=1.0,
                    help="Costo por hora de trabajo regular.")
            with col2:
                COt = st.number_input("Costo horas extra (COt)", value=15.0, step=1.0,
                    help="Costo por hora adicional trabajada fuera del turno regular.")
            with col3:
                CW_mas = st.number_input("Costo contratación (CW+)", value=100.0, step=1.0,
                    help="Costo asociado a incorporar nuevo personal.")
            with col4:
                CW_menos = st.number_input("Costo despido (CW-)", value=200.0, step=1.0,
                    help="Costo asociado a despidos o reducciones de personal.")

            # Sub-sección: estructura de turnos
            st.markdown("##### 🕓 Estructura de turnos")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                trabajadores_por_turno = st.number_input("👥 Trabajadores por turno", min_value=1, value=10, step=1)
            with col2:
                turnos_por_dia = st.number_input("🌙 Turnos por día", min_value=1, max_value=3, value=3, step=1)
            with col3:
                horas_por_turno = st.number_input("⏱️ Horas por turno", min_value=1, max_value=12, value=8, step=1)
            with col4:
                dias_mes = st.number_input("📅 Días operativos por mes", min_value=1, max_value=31, value=30, step=1)

            col1, col2 = st.columns(2)
            with col1:
                eficiencia = st.slider("⚡ Eficiencia operativa (%)", 50, 110, 95)
            with col2:
                ausentismo = st.slider("🚫 Ausentismo (%)", 0, 30, 5)


            # Cálculo de fuerza laboral efectiva
            LR_inicial = (
                trabajadores_por_turno
                * turnos_por_dia
                * horas_por_turno
                * dias_mes
                * (eficiencia / 100)
                * (1 - ausentismo / 100)
            )

            st.markdown(
                f"""
                <div style='
                    background-color:rgba(0, 123, 255, 0.08);
                    border:1px solid rgba(0, 123, 255, 0.25);
                    padding:10px 15px;
                    border-radius:10px;
                    text-align:center;
                    margin-top:12px;
                '>
                    💪 <b>Capacidad laboral efectiva:</b> 
                    <span style='font-size:18px; color:#007bff;'>{LR_inicial:,.0f}</span> horas-hombre / período
                </div>
                """,
                unsafe_allow_html=True
            )

            st.divider()

            # =========================
            # 🧮 PARÁMETROS TÉCNICOS
            # =========================
            st.markdown("#### 🧮 Parámetros técnicos")
            col1, col2= st.columns(2)
            with col1:
                M = st.number_input("Horas requeridas por unidad (M)", value=1.0, step=0.1, help="Cuántas horas-hombre se necesitan para producir una unidad de producto.")
            with col2:
                max_des_contrat = st.number_input("Máximo de contratación/despido mensual", min_value = 0, value=20, step=1)



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
            emp_in = trabajadores_por_turno*turnos_por_dia,
            horas_turno= horas_por_turno,
            inv_seg=inv_seg,
            turnos_dia = turnos_por_dia,
            dias_mes = dias_mes,
            eficiencia = (eficiencia-ausentismo)/100,
            delta_trabajadores = max_des_contrat
        )
        st.plotly_chart(fig_df_plan_agg, config={"responsive": True}, use_container_width=True)
        st.dataframe(df_plan_agg.reset_index(drop=True), width='stretch')

    # Tab 3: Planeación Desagregada
    with tab3:
        st.subheader("Producción Desagregada por Producto")
        with st.expander("⚙️ Ajuste de parámetros de desagregación", expanded=True):
            st.markdown(
                """
                Define los **costos asociados al modelo de desagregación** para equilibrar la 
                producción y el inventario. Un ajuste adecuado permite minimizar los excesos de stock sin afectar la disponibilidad del producto.
                """
            )

            col1, col2 = st.columns(2)

            with col1:
                cost_prod_ = st.number_input(
                    "🏭 Costo de Producción (Ct)",
                    min_value=0.1,
                    value=1.0,
                    step=0.1,
                    key="cost_prod_tab3",
                    help="Costo directo de fabricar una unidad del producto. Un valor alto incentiva producir menos."
                )

            with col2:
                cost_inv_ = st.number_input(
                    "📦 Costo de Inventario (Ht)",
                    min_value=0.1,
                    value=1.0,
                    step=0.1,
                    key="cost_inv_tab3",
                    help="Costo de mantener inventario entre períodos. Un valor alto incentiva producir bajo demanda."
                )

            # Pequeña tarjeta visual resumen
            st.markdown(
                f"""
                <div style='
                    background-color:rgba(0,0,0,0.05);
                    padding:12px;
                    border-radius:8px;
                    margin-top:10px;
                    text-align:center;
                '>
                    💡 <b>Interpretación:</b>  
                    Si <span style='color:#00796B;'>Ht &gt; Ct</span>, el modelo tenderá a producir más ajustado a la demanda.  
                    Si <span style='color:#D32F2F;'>Ct &gt; Ht</span>, priorizará reducir la producción incluso si sube el inventario.
                </div>
                """,
                unsafe_allow_html=True
            )



        st.markdown("Esta planeación distribuye la producción agregada entre los diferentes productos, permitiendo visualizar inventarios finales y producción asignada por producto y período.")
        df_prod, df_inv_desagg, df_resultado, fig_desagg = desagregar_produccion(
            demanda_df=edited_demanda,
            df_inventario_inicial=inventario_inicial(porc_part=porc_part),
            resultados=df_plan_agg,
            num_per=num_per,
            cost_prod=cost_prod_,
            cost_inv=cost_inv_
        )
        
        st.markdown("## 📊 Visualización de la Desagregación")
        st.plotly_chart(fig_desagg, use_container_width=True, config={"responsive": True})
        
        # =============================
        # SECCIÓN: Resultados desagregados
        # =============================

        st.markdown("## 🔎 Resultados desagregados")
        st.markdown(
            """
            Visualiza la **producción e inventario mensual por tipo de bebida**.  
            Estos resultados provienen del modelo de desagregación y permiten analizar la distribución de recursos entre productos.
            """
        )

        # --- Producción ---
        with st.container():
            st.markdown(
                """
                <div style='
                    background-color:rgba(0, 150, 136, 0.1);
                    padding:10px;
                    border-radius:8px;
                    margin-bottom:10px;
                    border-left:4px solid #009688;
                '>
                    🏭 <b>Producción desagregada</b><br>
                    Muestra la cantidad planificada por producto y período.
                </div>
                """,
                unsafe_allow_html=True
            )
            st.dataframe(
                df_prod.reset_index(drop=True),
                width='stretch',
                hide_index=True,
                height=300
            )

        # --- Inventario ---
        with st.container():
            st.markdown(
                """
                <div style='
                    background-color:rgba(255, 193, 7, 0.1);
                    padding:10px;
                    border-radius:8px;
                    margin-top:25px;
                    margin-bottom:10px;
                    border-left:4px solid #FFC107;
                '>
                    📦 <b>Inventario desagregado</b><br>
                    Representa el inventario final por producto y mes, luego de aplicar la política de producción.
                </div>
                """,
                unsafe_allow_html=True
            )
            st.dataframe(
                df_inv_desagg.reset_index(drop=True),
                width='stretch',
                hide_index=True,
                height=300
            )


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
            
            # --- PARÁMETROS GENERALES ---
            st.markdown("### 🏭 Parámetros operativos")
            col1, col2, col3 = st.columns(3)
            with col1:
                horas_dia = st.number_input("Horas por jornada", 1, 8, 8, key="sim_horas_dia")
            with col2:
                dias_mes = st.number_input("Días por mes", 1, 31, 30, key="sim_dias_mes")
            with col3:
                turnos_por_dia = st.number_input("Turnos por día", 1, 3, 3, key="sim_turnos_dia")

            st.divider()

            # --- CAPACIDAD INSTALADA ---
            st.markdown("### ⚙️ Capacidad de estaciones")
            col1, col2, col3 = st.columns(3)
            with col1:
                num_mezcla = st.number_input("Equipos de mezcla", 1, 20, 1, key="sim_num_mezcla")
                num_pasteurizacion = st.number_input("Pasteurizadores", 1, 20, 1, key="sim_num_pasteurizacion")
            with col2:
                num_llenado = st.number_input("Líneas de llenado", 1, 20, 1, key="sim_num_llenado")
                num_etiquetado = st.number_input("Estaciones de etiquetado", 1, 20, 1, key="sim_num_etiquetado")
            with col3:
                num_camaras = st.number_input("Cámaras de refrigeración", 1, 20, 1, key="sim_num_camaras")

            st.divider()

            # --- TIEMPOS DE PROCESO ---
            st.markdown("### ⏱️ Tiempos de proceso (minutos)")
            col1, col2, col3 = st.columns(3)
            with col1:
                tiempo_mezcla = st.slider("Mezcla", 0, 120, (15, 25), key="sim_tiempo_mezcla")
                tiempo_pasteurizacion = st.slider("Pasteurización", 1, 120, (30, 45), key="sim_tiempo_pasteurizacion")
            with col2:
                tiempo_llenado = st.slider("Llenado", 0, 120, (10, 15), key="sim_tiempo_llenado")
                tiempo_etiquetado = st.slider("Etiquetado", 0, 120, (20, 20), key="sim_tiempo_etiquetado")
            with col3:
                tiempo_almacenamiento = st.slider("Almacenamiento", 0, 60, (0, 0), key="sim_tiempo_almacenamiento")
        n_iter = st.number_input("Iteraciones de simulación", 2, 100, 2, key="sim_iteraciones")
        if st.button("🚀 Ejecutar simulación"):
            with st.spinner("Simulando producción según el plan desagregado..."):
                try:
                    df_sim_resultados, df_sim_utilizacion, df_sim_metricas = simular_produccion(
                        df_desagregacion=df_prod,
                        tamano_lote_max=tamano_lote,
                        num_mezcla=num_mezcla,
                        num_pasteurizacion=num_pasteurizacion,
                        num_llenado=num_llenado,
                        num_etiquetado=num_etiquetado,
                        num_camaras=num_camaras,
                        horas_dia=horas_dia,
                        dias_mes=dias_mes,
                        litros_por_unidad=litros_por_unidad,
                        tiempo_mezcla=tiempo_mezcla,
                        tiempo_pasteurizacion=tiempo_pasteurizacion,
                        tiempo_llenado=tiempo_llenado,
                        tiempo_etiquetado=tiempo_etiquetado,
                        tiempo_almacenamiento=tiempo_almacenamiento,
                        n_iter=n_iter,
                        turnos_por_dia=turnos_por_dia,
                        df_plan_agg = df_plan_agg
                    )
                except RuntimeError as e:
                    st.error(f"⚠️ Simulación detenida: {e}")
                else:
                    # --- Verificar saturación de recursos ---
                    exceso = df_sim_utilizacion[
                        (df_sim_utilizacion["Utilizacion"] > 1) &
                        (df_sim_utilizacion["Recurso"] != "Camaras")
                    ]
                    if not exceso.empty:
                        st.error("❌ Se superó la capacidad en los siguientes recursos:")

                        # Mostrar solo la primera fila de cada recurso (evita duplicados)
                        exceso_unico = exceso.drop_duplicates(subset=["Recurso"])

                        for _, row in exceso_unico.iterrows():
                            st.write(
                                f"- {row['Recurso']}: utilización {row['Utilizacion']*100:.2f}% (>100%) "
                            )
                    else:
                        st.success("✅ Simulación completada")                        
                        
                        # === MÉTRICAS GLOBALES ===
                        st.markdown("### 📊 Métricas globales de producción")

                        def mean_ci(series, conf=0.95):
                            """Calcula promedio y halfwidth (IC 95%)."""
                            if len(series) <= 1:
                                return series.mean(), 0
                            mean = np.mean(series)
                            sem = stt.sem(series, nan_policy='omit')
                            h = sem * stt.t.ppf((1 + conf) / 2., len(series) - 1)
                            return mean, h

                        if not df_sim_metricas.empty:
                            wip_m, wip_h = mean_ci(df_sim_metricas["WIP"])
                            cycle_m, cycle_h = mean_ci(df_sim_metricas["Cycle_time"])
                            throughput_m, throughput_h = mean_ci(df_sim_metricas["Throughput"])
                            takt_m, takt_h = mean_ci(df_sim_metricas["Takt_time"])

                            col1, col2, col3, col4 = st.columns(4)
                            col1.metric(f"🧱 WIP (Work in Process)", f"{wip_m:.2f} ± {wip_h:.2f}")
                            col2.metric(f"⏱️ Cycle Time (min)", f"{cycle_m:.2f} ± {cycle_h:.2f}")
                            col3.metric(f"⚡ Throughput (lotes/min)", f"{throughput_m:.3f} ± {throughput_h:.3f}")
                            col4.metric(f"📏 Takt Time (min/lote)", f"{takt_m:.2f} ± {takt_h:.2f}")

                        # === UTILIZACIÓN DE RECURSOS ===
                        st.markdown("### ⚙️ Utilización de recursos")

                        df_util = (
                            df_sim_utilizacion[df_sim_utilizacion["Recurso"] != "Camaras"]
                            .groupby("Recurso", as_index=False)
                            .agg({"Utilizacion": list})
                        )

                        if not df_util.empty:
                            n_cols = min(4, len(df_util))
                            cols = st.columns(n_cols)

                            for i, (_, row) in enumerate(df_util.iterrows()):
                                recurso = row["Recurso"]
                                util_list = row["Utilizacion"]
                                mean_val, h_val = mean_ci(util_list)
                                valor = mean_val * 100
                                halfwidth = h_val * 100

                                color = "#00cc96" if valor < 80 else "#ffa726" if valor < 95 else "#ef5350"

                                fig = go.Figure(go.Indicator(
                                    mode="gauge+number",
                                    value=valor,
                                    number={"suffix": f"%", "font": {"size": 40}},
                                    gauge={
                                        "axis": {"range": [0, 100], "tickwidth": 0, "visible": False},
                                        "bar": {"color": color, "thickness": 1.0},
                                        "bgcolor": "#f8f9fa",
                                        "borderwidth": 0,
                                        "shape": "angular"
                                    },
                                    title={"text": f"{recurso} ± {halfwidth:.2f}", "font": {"size": 18}}
                                ))

                                fig.update_layout(
                                    height=180,
                                    margin=dict(l=5, r=5, t=30, b=50),
                                    template="plotly_white",
                                )

                                cols[i % n_cols].plotly_chart(fig, use_container_width=True)

                        else:
                            st.info("No hay datos de utilización disponibles.")
                        
                        # === RESUMEN DE LOTES ===
                        df_lotes_resumen = (
                            df_sim_resultados
                            .groupby(["Bebida", "Periodo"])
                            .agg(
                                Cantidad_lotes=("Lote", "count"),
                                Litros_fabricados=("Tamano_botellas", "sum")
                            )
                            .reset_index()
                        )
                        df_lotes_resumen = df_lotes_resumen.sort_values(
                            ['Periodo', 'Cantidad_lotes', 'Bebida'],
                            ascending=[True, False, True]
                        ).reset_index(drop=True)

                        df_lotes_resumen["Litros_fabricados"] *= litros_por_unidad
                        df_lotes_resumen["Unidades_fabricadas"] = (
                            df_lotes_resumen["Litros_fabricados"] / litros_por_unidad
                        )
                                        
                        fig_sim = grafica_simulacion_resumen(df_lotes_resumen=df_lotes_resumen, modo='porcentaje')
                        st.plotly_chart(fig_sim, config={"responsive": True}, use_container_width=True)

                        with st.expander("📦 Ver detalle de lotes", expanded=False):
                            st.dataframe(df_lotes_resumen, width='stretch')

                        csv = df_sim_resultados.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            "⬇️ Descargar resultados completos simulación (CSV)",
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
    

import plotly.graph_objects as go

def grafica_simulacion_resumen(df_lotes_resumen, modo="volumen"):
    """
    🔥 Mapa de calor de producción por bebida a lo largo de los meses.
    
    Parámetros:
    -----------
    df_lotes_resumen : pd.DataFrame
        Contiene columnas: ["Mes", "Bebida", "Litros_fabricados"]
    modo : str
        "volumen" → muestra litros fabricados
        "porcentaje" → muestra participación (% del total mensual)
    """

    df = df_lotes_resumen.copy()

    # Pivotar para tener bebidas como filas y meses como columnas
    pivot = df.pivot(index="Bebida", columns="Periodo", values="Litros_fabricados").fillna(0)

    if modo == "porcentaje":
        pivot = pivot.div(pivot.sum(axis=0), axis=1) * 100
        z_title = "% del total mensual"
        colorscale = "BuPu"
        hovertemplate = "Bebida: %{y}<br>Mes: %{x}<br>Participación: %{z:.1f}%<extra></extra>"
    else:
        z_title = "Litros fabricados"
        colorscale = "BuPu"
        hovertemplate = "Bebida: %{y}<br>Mes: %{x}<br>Producción: %{z:,.0f} L<extra></extra>"

    # Crear el heatmap
    fig = go.Figure(
        data=go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            colorscale=colorscale,
            colorbar=dict(title=z_title),
            hovertemplate=hovertemplate
        )
    )

    # Ajustes visuales
    fig.update_layout(
        title=dict(
            text="🏭 Mapa de calor de producción por bebida",
            x=0.5, xanchor="center", font=dict(size=18)
        ),
        xaxis=dict(title="Mes", tickmode="linear", tickfont=dict(size=12)),
        yaxis=dict(title="Bebida", tickfont=dict(size=12)),
        height=500,
        template="plotly_white",
        margin=dict(l=60, r=40, t=80, b=50)
    )

    return fig

