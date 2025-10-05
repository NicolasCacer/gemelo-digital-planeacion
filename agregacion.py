import pandas as pd
from pulp import *
import plotly.graph_objects as go

def planeacion_agregada_completa(
    demanda_df,
    inv_in_df,
    num_per,
    inv_inicial=0.2,
    Ct=10, Ht=10, CRt=10, COt=10, PIt=1e10, CW_mas=100, CW_menos=200,
    M=1, LR_inicial = 10 * 160, inv_seg= 0.05 
):
    df_demanda_mensual = demanda_df.iloc[-num_per*5:]

    # Planeación Agregada

    anio_base = df_demanda_mensual['anio'].min()

    # Calcular mes continuo
    df_demanda_mensual = df_demanda_mensual.assign(
        mes_continuo=lambda x: (x['anio'] - anio_base) * 12 + x['mes']
    )

    # Sumar demanda por mes_continuo (todas las bebidas)
    # Sumar demanda por mes_continuo y redondear a 2 decimales
    demanda_por_mes = (
        df_demanda_mensual
        .groupby('mes_continuo')['demanda_esperada']
        .sum()
        .round(2)
        .to_dict()
    )


    # ===============================
    # 1) PARÁMETROS
    # ===============================
    demanda_t = demanda_por_mes
    periodos = list(demanda_t.keys())
    inv_inicial = inv_in_df['inventario_inicial'].sum()

    Ct = 80
    M = 1          # cuantas horas-hombre para hacer 1 unidad
    Ht = 2.70
    PIt = 1E99     # backlog prohibido
    CRt = 12
    COt = 18
    CW_mas = 10
    CW_menos = 37
    # Capacidad inicial de horas regulares (mes 1)
    # Supongamos que tienes 10 operarios, cada uno disponible 160 horas al mes
    LR_inicial = 10 * 160  # 1600 horas


    # Inventario mínimo proporcional a demanda mensual
    inv_min_t = {t: inv_seg*demanda_t[t] for t in periodos}  # 5% de la demanda

    # Máximos de contratación/despidos por periodo
    max_contratacion = 50000
    max_despidos = 50000

    # ===============================
    # 2) DEMANDA NETA
    # ===============================
    demanda_neta_t = demanda_t.copy()
    primer_periodo = min(periodos)
    demanda_neta_t[primer_periodo] = max(demanda_t[primer_periodo] - inv_inicial, 0)

    # ===============================
    # 3) MODELO
    # ===============================
    plan_agg_flow = LpProblem("Minimizar_costos_agregados_flujo", LpMinimize)

    # Variables de decisión
    P = LpVariable.dicts("P", periodos, lowBound=0)
    I = LpVariable.dicts("I", periodos, lowBound=0)
    S = LpVariable.dicts("S", periodos, lowBound=0)  # backlog
    LR = LpVariable.dicts("LR", periodos, lowBound=0)
    LO = LpVariable.dicts("LO", periodos, lowBound=0)
    W_mas = LpVariable.dicts("W_mas", periodos, lowBound=0, upBound=max_contratacion)
    W_menos = LpVariable.dicts("W_menos", periodos, lowBound=0, upBound=max_despidos)

    # Auxiliares
    NI = LpVariable.dicts("NI", periodos)
    LU = LpVariable.dicts("LU", periodos, lowBound=0)

    # ===============================
    # 4) FUNCIÓN OBJETIVO
    # ===============================
    plan_agg_flow += lpSum(
        Ct*P[t] + 
        CRt*LR[t] + 
        COt*LO[t] + 
        Ht*I[t] + 
        PIt*S[t] + 
        CW_mas*W_mas[t] + 
        CW_menos*W_menos[t]
        for t in periodos
    )

    # ===============================
    # 5) RESTRICCIONES
    # ===============================

    # Balance inventario neto usando demanda neta para el primer mes
    for t in periodos:
        if t == primer_periodo:
            plan_agg_flow += NI[t] == 0 + P[t] - demanda_neta_t[t], f"NI_ini_{t}"
        else:
            plan_agg_flow += NI[t] == NI[t-1] + P[t] - demanda_t[t], f"NI_balance_{t}"

    # Relación NI = I - S
    for t in periodos:
        plan_agg_flow += NI[t] == I[t] - S[t], f"NI_def_{t}"

    # Balance de horas
    for t in periodos:
        plan_agg_flow += LU[t] + LO[t] == M * P[t], f"horas_balance_{t}"

    # Evolución fuerza laboral
    for t in periodos:
        if t == 1:
            plan_agg_flow += LR[t] == LR_inicial + W_mas[t] - W_menos[t], f"LR_ini_{t}"
        else:
            plan_agg_flow += LR[t] == LR[t-1] + W_mas[t] - W_menos[t], f"LR_balance_{t}"

    # Inventario mínimo por periodo
    for t in periodos:
        plan_agg_flow += I[t] >= inv_min_t[t], f"inv_min_{t}"

    # Las horas regulares pueden cubrir hasta LR[t] unidades
    # Las horas extras pueden cubrir LO[t] unidades
    for t in periodos:
        plan_agg_flow += P[t] <= LR[t]/M + LO[t]/M


    # ===============================
    # 6) SOLVER
    # ===============================
    plan_agg_flow.solve()

    print(f"\nModelo: {plan_agg_flow.name}")
    print("Estado:", LpStatus[plan_agg_flow.status])
    costo_total = value(plan_agg_flow.objective)
    print(f"Costo mínimo: ${costo_total:,.1f}")

    # ===============================
    # 7) RESULTADOS EN TABLA
    # ===============================
    resultados = pd.DataFrame({
        "Periodo": periodos,
        "Demanda": [demanda_neta_t[t] for t in periodos],
        "Producción": [P[t].varValue for t in periodos],
        "Inventario": [I[t].varValue for t in periodos],
        "Backlog": [S[t].varValue for t in periodos],
        "Horas_Regulares": [LR[t].varValue for t in periodos],
        "Horas_Extras": [LO[t].varValue for t in periodos],
        "Contratación": [W_mas[t].varValue for t in periodos],
        "Despidos": [W_menos[t].varValue for t in periodos],
        "Inventario_Neto": [NI[t].varValue for t in periodos],
        "Uso_Horas": [LU[t].varValue for t in periodos],
    })
    resultados = resultados.round(1)
    
    # ===============================
    # 7) GRAFICAR
    # ===============================
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=resultados["Periodo"], y=resultados["Producción"],
        name="Producción", marker_color="steelblue"
    ))
    fig.add_trace(go.Bar(
        x=resultados["Periodo"], y=resultados["Inventario"],
        name="Inventario", marker_color="darkorange"
    ))
    fig.add_trace(go.Bar(
        x=resultados["Periodo"], y=resultados["Backlog"],
        name="Backlog", marker_color="crimson"
    ))
    fig.add_trace(go.Scatter(
        x=resultados["Periodo"], y=resultados["Demanda"],
        mode='lines+markers', name="Demanda",
        line=dict(color='green', dash='dash')
    ))

    fig.update_layout(
        title=f"Plan Agregado (Costo óptimo: ${costo_total:,.0f})",
        xaxis_title="Periodo", yaxis_title="Cantidad",
        barmode='group', template="plotly_white",
        xaxis=dict(
            tickmode='linear',     # asegura que cada tick se muestre
            dtick=1                # cada 1 unidad en el eje x
        )
    )
    return resultados, fig
