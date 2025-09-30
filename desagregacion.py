import pandas as pd
from pulp import *

def desagregar_produccion(df_plan, P_prod=3700):
    """
    Desagrega la producción mensual planificada de planeacion_agregada_completa
    a producción mensual (por mes) usando un algoritmo de ciclo máximo considerando inventario inicial.
    
    df_plan: DataFrame con columnas al menos:
        - 'Mes' (ej. "Mes 1")
        - 'Produccion' (producción mensual planificada)
        - 'Inventario' (inventario al inicio del mes)
    P_prod: capacidad de producción mensual
    """
    
    df = df_plan.copy()
    
    # Convertir columna Mes a número
    df['Mes_num'] = df['Mes'].apply(lambda x: int(x.split()[1]) if isinstance(x, str) else int(x))
    
    # Calcular inventario en meses
    df['Inv_meses'] = df['Inventario'] / df['Produccion']
    
    # Ordenar por menor inventario en meses
    df = df.sort_values('Inv_meses').reset_index(drop=True)
    
    referencias = df.index.tolist()
    demanda_k = {i: df.loc[i, 'Produccion'] for i in referencias}
    inv_ini = {i: df.loc[i, 'Inventario'] for i in referencias}
    
    # Razón inventario/demanda
    rt = {i: inv_ini[i]/demanda_k[i] if demanda_k[i] > 0 else 0 for i in referencias}
    
    # Modelo de optimización
    plan_desagg = LpProblem("Maximizar_tiempo_de_ciclo", LpMaximize)
    
    # Variables: tiempo de inicio de producción por mes
    t_i = LpVariable.dicts("t_i", referencias, lowBound=0)
    
    # Objetivo: maximizar el tiempo de inicio del último mes
    plan_desagg += t_i[referencias[-1]]
    
    # Restricciones de inventario (no desabastecer)
    for i in referencias:
        plan_desagg += t_i[i] <= rt[i]
    
    # Restricciones de producción vs demanda: tiempo necesario para producir
    for i in range(len(referencias)-1):
        plan_desagg += t_i[i+1] - t_i[i] >= demanda_k[i] / P_prod
    
    # Restricción para el último mes
    plan_desagg += t_i[referencias[-1]] >= demanda_k[referencias[-1]] / P_prod
    
    # Resolver
    plan_desagg.solve()
    
    # Guardar resultados
    df['Tiempo_inicio_mes'] = [t_i[i].varValue for i in referencias]
    df['Produccion_mes'] = df['Produccion']  # ya mensual
    
    # Orden original de meses
    df = df.sort_values('Mes_num').reset_index(drop=True)
    
    return df
