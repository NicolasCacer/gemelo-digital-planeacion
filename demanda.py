import pandas as pd
# Encuesta Anual Manufacturera (EAM) Históricos - Base 2023
# Fuente: (https://www.dane.gov.co/index.php/estadisticas-por-tema/industria/encuesta-anual-manufacturera-enam/eam-historicos)
EAM_2023_datos = {
    "articulo": ["Bebidas gaseosas no alcohólicas (maltas, gaseosas, etc.)",
                 "Bebidas no alcohólicas sin gasificar-refrescos"],
    "unidad_medida": ["Litros",
                      "Litros"],
    "ventas_cantidad": [4088736317,
                        951434414],
    "Inventario_cantidad_31_dic": [234404972,
                                   44604232]
}
df_EAM_2023 = pd.DataFrame(EAM_2023_datos)


# Encuesta mensual manufacturera con enfoque territorial (EMMET) Históricos
# Fuente: (https://www.dane.gov.co/index.php/estadisticas-por-tema/industria/encuesta-mensual-manufacturera-con-enfoque-territorial-emmet/emmet-historicos)

EMMET_2024_datos = {
    "mes": list(range(1, 13)),
    "clase_industrial": ["Elaboración de bebidas"]*12,
    "produccion_nominal": [154.0, 137.7, 140.5, 149.3, 151.5, 155.5, 162.5, 165.6, 159.2, 169.8, 172.7, 184.9],
    "produccion_real": [129.0, 115.5, 116.0, 122.5, 124.1, 128.6, 134.5, 136.4, 130.6, 140.2, 142.8, 151.2],
    "ventas_nominales": [151.2, 132.8, 138.7, 148.3, 149.7, 149.9, 161.5, 163.3, 157.9, 165.7, 174.7, 195.8],
    "ventas_reales": [126.8, 111.1, 114.7, 121.9, 122.4, 124.2, 134.0, 134.7, 129.7, 137.1, 144.9, 160.5],
}
df_EMMET_2024 = pd.DataFrame(EMMET_2024_datos)


# Market share global de bebídas no alcohólicas
share_productos = {
    'agua':355118,
    'gaseosa': 194593,
    'concentrada':2987,
    'jugos':59985,
    'cafe': 5737,
    'te': 36592,
    'energeticas': 20974,
    'deportivas': 16515
}

df_share = pd.DataFrame(share_productos.items(), columns=['bebida', 'ventas'])
df_share['share'] = df_share['ventas'] / df_share['ventas'].sum()

def generar_pronostico_demanda(EAM_2023 = df_EAM_2023, EMMET_2024 = df_EMMET_2024, df_share = df_share):
    """
    Calcula la demanda mensual esperada por bebida.
    
    Parámetros:
        EAM_2023 (DataFrame): Ventas históricas 2023.
        EMMET_2024 (DataFrame): Índices mensuales de ventas reales 2024.
        df_share (DataFrame): Market share de cada bebida.
    
    Retorna:
        pd.DataFrame: Demanda mensual esperada por bebida.
    """
    
    # --- Paso 1: Normalizar índices mensuales de ventas reales ---
    EMMET_2024['ventas_proporcion'] = EMMET_2024['ventas_reales'] / EMMET_2024['ventas_reales'].sum()

    # --- Paso 2: Calcular venta total anual de 2023 ---
    ventas_totales_2023 = EAM_2023['ventas_cantidad'].sum() * 0.01*0.5

    # --- Paso 3: Crear DataFrame mensual base con ventas totales ---
    df_mensual = pd.DataFrame({
        'mes': EMMET_2024['mes'],
        'ventas_mes_total': EMMET_2024['ventas_proporcion'] * ventas_totales_2023
    })

    # --- Paso 4: Distribuir entre productos según market share ---
    df_share['share'] = df_share['share'] / df_share['share'].sum()

    resultados = []
    for _, row_mes in df_mensual.iterrows():
        for _, row_prod in df_share.iterrows():
            demanda = row_mes['ventas_mes_total'] * row_prod['share']
            resultados.append({
                'mes': row_mes['mes'],
                'bebida': row_prod['bebida'],
                'demanda_esperada': int(round(demanda))  # Redondeo a entero
            })

    df_demanda_mensual = pd.DataFrame(resultados)
    return df_demanda_mensual
