import pandas as pd
from pulp import *

def planeacion_agregada_completa(
    demanda_df, 
    costos_df, 
    categoria_agregar,
    inv_inicial=10,
    Ct=10, Ht=10, CRt=10, COt=10, PIt=1e10, CW_mas=100, CW_menos=200,
    M=1
):
    """
    Planeación agregada considerando coeficientes de consumo de recursos.
    """
    # ---------- Preparar meses ----------
    # Convertir todos los meses de demanda_df a string "Mes N"
    demanda_df = demanda_df.copy()
    demanda_df['Mes_str'] = demanda_df['Mes'].apply(lambda x: f'Mes {int(x)}')
    meses = sorted(demanda_df['Mes_str'].unique(), key=lambda x: int(x.split()[1]))
    
    # ---------- Calcular demanda agregada ----------
    demanda_agregada = pd.DataFrame({'Mes': meses, 'Demanda': 0.0})
    
    productos_categoria = costos_df[costos_df['Categoría']==categoria_agregar]['Producto'].unique()
    
    for mes in meses:
        demanda_total = 0
        for prod in productos_categoria:
            if mes not in costos_df.columns:
                raise ValueError(f"El mes {mes} no existe en costos_df")
            coef = costos_df.loc[
                (costos_df['Categoría']==categoria_agregar) &
                (costos_df['Producto']==prod),
                mes
            ].values[0]
            demanda_prod = demanda_df.loc[
                (demanda_df['Producto']==prod) &
                (demanda_df['Mes_str']==mes),
                'Demanda'
            ].values
            if len(demanda_prod) > 0:
                demanda_total += demanda_prod[0] * coef
        demanda_agregada.loc[demanda_agregada['Mes']==mes,'Demanda'] = demanda_total
    
    # ---------- Definir modelo ----------
    plan = LpProblem("Planeacion_Agregada", LpMinimize)
    
    P = LpVariable.dicts("P", meses, lowBound=0)
    I = LpVariable.dicts("I", meses, lowBound=0)
    S = LpVariable.dicts("S", meses, lowBound=0)
    LR = LpVariable.dicts("LR", meses, lowBound=0)
    LO = LpVariable.dicts("LO", meses, lowBound=0)
    W_mas = LpVariable.dicts("W_mas", meses, lowBound=0)
    W_menos = LpVariable.dicts("W_menos", meses, lowBound=0)
    NI = LpVariable.dicts("NI", meses)
    LU = LpVariable.dicts("LU", meses, lowBound=0)
    
    # ---------- Función objetivo ----------
    plan += lpSum([
        Ct*P[m] + CRt*LR[m] + COt*LO[m] + Ht*I[m] + PIt*S[m] + CW_mas*W_mas[m] + CW_menos*W_menos[m]
        for m in meses
    ])
    
    # ---------- Restricciones ----------
    for i, m in enumerate(meses):
        if i == 0:
            plan += NI[m] == inv_inicial + P[m] - demanda_agregada.loc[demanda_agregada['Mes']==m,'Demanda'].values[0]
        else:
            plan += NI[m] == NI[meses[i-1]] + P[m] - demanda_agregada.loc[demanda_agregada['Mes']==m,'Demanda'].values[0]
        plan += NI[m] == I[m] - S[m]
        
        if i > 0:
            plan += LR[m] == LR[meses[i-1]] + W_mas[m] - W_menos[m]
        plan += LO[m] - LU[m] == M*P[m] - LR[m]
    
    plan.solve(PULP_CBC_CMD(msg=0))
    
    # ---------- Resultados ----------
    resultados = []
    for m in meses:
        resultados.append({
            'Mes': m,
            'Demanda_agregada': demanda_agregada.loc[demanda_agregada['Mes']==m,'Demanda'].values[0],
            'Produccion': P[m].varValue,
            'Inventario': I[m].varValue,
            'Backorder': S[m].varValue,
            'Horas_regulares': LR[m].varValue,
            'Horas_extras': LO[m].varValue,
            'Contratacion': W_mas[m].varValue,
            'Despidos': W_menos[m].varValue
        })
    
    df_resultados = pd.DataFrame(resultados)
    return df_resultados
