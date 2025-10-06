import pandas as pd
from pulp import *
import plotly.graph_objects as go

def planeacion_agregada_completa(
    demanda_df,
    inv_in_df,
    num_per,
    Ct=10, Ht=10, CRt=10, COt=10, PIt=1e10, CW_mas=100, CW_menos=200,
    M=1, horas_turno=8, inv_seg= 0.0, emp_in = 10, turnos_dia = 3, dias_mes = 30, eficiencia = 0.9, delta_trabajadores = 100
):
    df_demanda_mensual = demanda_df.iloc[-num_per*5:]
    anio_base = df_demanda_mensual['anio'].min()
    df_demanda_mensual = df_demanda_mensual.assign(
        mes_continuo=lambda x: (x['anio'] - anio_base) * 12 + x['mes']
    )
    demanda_por_mes = (
        df_demanda_mensual.groupby('mes_continuo')['demanda_esperada']
        .sum().round(2).to_dict()
    )

    # ===============================
    demanda_t = demanda_por_mes
    periodos = sorted(list(demanda_t.keys()))
    primer_periodo = min(periodos)
    inv_inicial = inv_in_df['inventario_inicial'].sum()
    horas_por_empleado = horas_turno * turnos_dia * dias_mes * eficiencia
 # ejemplo, ajustar según caso
    empleados_inicial = emp_in

    Ct = 80; M = 1; Ht = 2.70; PIt = 1E99
    CRt = 12; COt = 18; CW_mas = 10; CW_menos = 37
    inv_min_t = {t: inv_seg*demanda_t[t] for t in periodos}
    max_contratacion = delta_trabajadores
    max_despidos = delta_trabajadores

    # Demanda neta
    demanda_neta_t = demanda_t.copy()
    demanda_neta_t[primer_periodo] = max(demanda_t[primer_periodo] - inv_inicial, 0)

    # ===============================
    plan_agg_flow = LpProblem("Minimizar_costos_agregados_flujo", LpMinimize)

    # Variables de decisión
    P = LpVariable.dicts("P", periodos, lowBound=0)
    I = LpVariable.dicts("I", periodos, lowBound=0)
    S = LpVariable.dicts("S", periodos, lowBound=0)
    LO = LpVariable.dicts("LO", periodos, lowBound=0)
    W_mas = LpVariable.dicts("W_mas", periodos, lowBound=0, upBound=max_contratacion, cat="Integer")
    W_menos = LpVariable.dicts("W_menos", periodos, lowBound=0, upBound=max_despidos, cat="Integer")
    Empleados = LpVariable.dicts("Empleados", periodos, lowBound=0, cat="Integer")
    LR = LpVariable.dicts("LR", periodos, lowBound=0)  # horas regulares
    NI = LpVariable.dicts("NI", periodos)
    LU = LpVariable.dicts("LU", periodos, lowBound=0)

    # ===============================
    plan_agg_flow += lpSum(
        Ct*P[t] + CRt*LR[t] + COt*LO[t] + Ht*I[t] + PIt*S[t] +
        CW_mas*W_mas[t] + CW_menos*W_menos[t] for t in periodos
    )

    # ===============================
    for t in periodos:
        # Inventario neto
        if t == primer_periodo:
            plan_agg_flow += NI[t] == P[t] - demanda_neta_t[t], f"NI_ini_{t}"
        else:
            plan_agg_flow += NI[t] == NI[t-1] + P[t] - demanda_t[t], f"NI_balance_{t}"
        plan_agg_flow += NI[t] == I[t] - S[t], f"NI_def_{t}"

        # Horas necesarias
        plan_agg_flow += LU[t] + LO[t] == M * P[t], f"horas_balance_{t}"
        plan_agg_flow += LU[t] <= LR[t], f"LU_no_mas_LR_{t}"
        plan_agg_flow += I[t] >= inv_min_t[t], f"inv_min_{t}"

        # Capacidad por horas
        plan_agg_flow += P[t] <= LR[t]/M + LO[t]/M, f"capacidad_horas_{t}"

    # ===============================
    for t in periodos:
        # Evolución empleados
        if t == primer_periodo:
            plan_agg_flow += Empleados[t] == empleados_inicial + W_mas[t] - W_menos[t], f"Empleados_ini_{t}"
            plan_agg_flow += W_menos[t] <= empleados_inicial, f"Despidos_max_ini_{t}"
        else:
            plan_agg_flow += Empleados[t] == Empleados[t-1] + W_mas[t] - W_menos[t], f"Empleados_balance_{t}"
            plan_agg_flow += W_menos[t] <= Empleados[t-1], f"Despidos_max_{t}"
        plan_agg_flow += LR[t] == Empleados[t] * horas_por_empleado, f"LR_def_{t}"
        plan_agg_flow += Empleados[t] >= 0, f"Empleados_no_neg_{t}"

    for t in periodos:
        plan_agg_flow += LR[t] == Empleados[t] * horas_por_empleado
    # ===============================
    plan_agg_flow.solve()
    costo_total = value(plan_agg_flow.objective)

    # ===============================
    # Resultados
    inv_inicial_list = []; inv_final_list = []
    for t in periodos:
        if t == primer_periodo:
            inv_inicial_list.append(inv_inicial)
        else:
            inv_inicial_list.append(inv_final_list[-1])
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
        "Empleados": [Empleados[t].varValue for t in periodos],
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
