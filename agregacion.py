import pandas as pd
from pulp import *
import plotly.graph_objects as go

def planeacion_agregada_completa(
    demanda_df,
    inv_in_df,
    num_per,
    Ct=10, Ht=10, CRt=10, COt=10, PIt=1e10, CW_mas=100, CW_menos=200,
    M=1, LR_inicial = 10 * 160, inv_seg= 0.0 
):
    df_demanda_mensual = demanda_df.iloc[-num_per*5:]

    # Planeación Agregada
    anio_base = df_demanda_mensual['anio'].min()

    # Calcular mes continuo
    df_demanda_mensual = df_demanda_mensual.assign(
        mes_continuo=lambda x: (x['anio'] - anio_base) * 12 + x['mes']
    )

    # Sumar demanda por mes_continuo (todas las bebidas)
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
    periodos = sorted(list(demanda_t.keys()))
    primer_periodo = min(periodos)
    inv_inicial = inv_in_df['inventario_inicial'].sum()

    Ct = 80
    M = 1          # cuantas horas-hombre para hacer 1 unidad
    Ht = 2.70
    PIt = 1E99     # backlog prohibido grande
    CRt = 12
    COt = 18
    CW_mas = 10
    CW_menos = 37
    LR_inicial = LR_inicial  # ya viene por argumento (ej: 1600)

    # Inventario mínimo proporcional a demanda mensual
    inv_min_t = {t: inv_seg*demanda_t[t] for t in periodos}  # p.e. 5% de la demanda

    # Máximos de contratación/despidos por periodo
    max_contratacion = 50000
    max_despidos = 50000

    # ===============================
    # 2) DEMANDA NETA
    # ===============================
    demanda_neta_t = demanda_t.copy()
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
    NI = LpVariable.dicts("NI", periodos)          # inventario neto (puede ser negativo)
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
    # Balance inventario neto usando demanda_neta para el primer mes
    for t in periodos:
        if t == primer_periodo:
            plan_agg_flow += NI[t] == 0 + P[t] - demanda_neta_t[t], f"NI_ini_{t}"
        else:
            plan_agg_flow += NI[t] == NI[t-1] + P[t] - demanda_t[t], f"NI_balance_{t}"

    # Relación NI = I - S
    for t in periodos:
        plan_agg_flow += NI[t] == I[t] - S[t], f"NI_def_{t}"

    # Balance de horas (uso de horas regulares + horas extras = horas necesarias para producir)
    for t in periodos:
        plan_agg_flow += LU[t] + LO[t] == M * P[t], f"horas_balance_{t}"

    # LU no puede exceder LR disponible (uso de horas regulares limitado)
    for t in periodos:
        plan_agg_flow += LU[t] <= LR[t], f"LU_no_mas_LR_{t}"

    # Evolución fuerza laboral: inicializar con primer_periodo (corrección importante)
    for t in periodos:
        if t == primer_periodo:
            plan_agg_flow += LR[t] == LR_inicial + W_mas[t] - W_menos[t], f"LR_ini_{t}"
        else:
            plan_agg_flow += LR[t] == LR[t-1] + W_mas[t] - W_menos[t], f"LR_balance_{t}"

    # Inventario mínimo por periodo
    for t in periodos:
        plan_agg_flow += I[t] >= inv_seg*inv_min_t[t], f"inv_min_{t}"

    # Las horas regulares + extras limitan producción
    for t in periodos:
        plan_agg_flow += P[t] <= LR[t]/M + LO[t]/M, f"capacidad_horas_{t}"

    # ===============================
    # 6) SOLVER
    # ===============================
    plan_agg_flow.solve()
    costo_total = value(plan_agg_flow.objective)


    # ===============================
    # 7) RESULTADOS EN TABLA MEJORADA
    # ===============================
    inv_inicial_periodo = inv_inicial  # Inventario inicial general
    inv_inicial_list = []
    inv_final_list = []

    for t in periodos:
        # Inventario inicial de cada periodo = inventario final del periodo anterior
        if t == primer_periodo:
            inv_inicial_list.append(inv_inicial_periodo)
        else:
            inv_inicial_list.append(inv_final_list[-1])
        
        # Inventario final = inventario inicial + producción - demanda
        inv_final = inv_inicial_list[-1] + P[t].varValue - demanda_t[t]
        inv_final_list.append(inv_final)

    resultados = pd.DataFrame({
        "Periodo": periodos,
        "Demanda": [demanda_t[t] for t in periodos],
        "Demanda_Neta": [demanda_neta_t[t] for t in periodos],
        "Producción": [P[t].varValue for t in periodos],
        "Inventario_Inicial": inv_inicial_list,
        "Inventario_Final": inv_final_list,
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
    # 8) GRAFICAR (producción + inventario apilados)
    # ===============================
    fig = go.Figure()

    # Barras apiladas: Producción + Inventario Inicial
    fig.add_trace(go.Bar(
        x=resultados["Periodo"], y=resultados["Inventario_Inicial"],
        name="Inventario Inicial", marker_color="darkorange",
        hovertemplate="Periodo %{x}<br>Inventario Inicial: %{y}<extra></extra>"
    ))
    fig.add_trace(go.Bar(
        x=resultados["Periodo"], y=resultados["Producción"],
        name="Producción", marker_color="lightblue",
        hovertemplate="Periodo %{x}<br>Producción: %{y}<extra></extra>"
    ))

    # Línea: Demanda total
    fig.add_trace(go.Scatter(
        x=resultados["Periodo"], y=resultados["Demanda"],
        mode='lines+markers', name="Demanda Total",
        line=dict(color='green', dash='dash', width=2),
        marker=dict(size=6),
        hovertemplate="Periodo %{x}<br>Demanda: %{y}<extra></extra>"
    ))

    # Layout
    fig.update_layout(
        title=f"Plan Agregado (Costo óptimo: ${costo_total:,.0f})",
        xaxis_title="Periodo (meses)",
        yaxis=dict(title="Litros", rangemode='tozero'),
        barmode='stack',  # <-- para apilar Inventario + Producción
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.01),
        hovermode="x unified",
        xaxis=dict(tickmode='linear', dtick=1)
    )


    return resultados, fig
