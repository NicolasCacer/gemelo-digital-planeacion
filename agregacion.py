import pandas as pd
from pulp import *

def planeacion_agregada(demanda_df, costo_produccion, costo_inventario):
    meses = demanda_df['Mes'].tolist()
    model = LpProblem("Planeacion_Agregada", LpMinimize)
    produccion = {mes: LpVariable(f'P_{mes}', lowBound=0) for mes in meses}

    model += lpSum([costo_produccion*produccion[mes] + costo_inventario*(produccion[mes]-demanda_df.loc[i,'Demanda'])
                    for i, mes in enumerate(meses)])

    for i, mes in enumerate(meses):
        model += produccion[mes] >= demanda_df.loc[i,'Demanda']

    model.solve()
    produccion_valores = [produccion[mes].varValue for mes in meses]
    demanda_df['Produccion_planificada'] = produccion_valores
    return demanda_df