def desagregar_produccion(produccion_df, dias_por_mes):
    produccion_diaria = [p/dias_por_mes for p in produccion_df['Produccion_planificada']]
    produccion_df['Produccion_diaria'] = produccion_diaria
    return produccion_df