import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX
import plotly.graph_objects as go
from plotly.colors import qualitative
import plotly.express as px

EAM_data = {
    2019: {
      "articulo": ["Bebidas gaseosas no alcohólicas (maltas, gaseosas, etc.)", "Bebidas no alcohólicas sin gasificar-refrescos"],
      "unidad_medida": ["Litros", "Litros"],
      "ventas_cantidad": [3446654269, 754553268],
      "Inventario_cantidad_31_dic": [101377860, 35811922]
    },
    2020: {
      "articulo": ["Bebidas gaseosas no alcohólicas (maltas, gaseosas, etc.)", "Bebidas no alcohólicas sin gasificar-refrescos"],
      "unidad_medida": ["Litros", "Litros"],
      "ventas_cantidad": [4194201705, 977976169],
      "Inventario_cantidad_31_dic": [113764872, 28067802]
    },
    2021: {
      "articulo": ["Bebidas gaseosas no alcohólicas (maltas, gaseosas, etc.)", "Bebidas no alcohólicas sin gasificar-refrescos"],
      "unidad_medida": ["Litros", "Litros"],
      "ventas_cantidad": [5096113399, 1339193257],
      "Inventario_cantidad_31_dic": [241123876, 84240002]
    },
    2022: {
      "articulo": ["Bebidas gaseosas no alcohólicas (maltas, gaseosas, etc.)", "Bebidas no alcohólicas sin gasificar-refrescos"],
      "unidad_medida": ["Litros", "Litros"],
      "ventas_cantidad": [6393545456, 1862877933],
      "Inventario_cantidad_31_dic": [174814383, 45413698]
    },
    2023: {
      "articulo": ["Bebidas gaseosas no alcohólicas (maltas, gaseosas, etc.)", "Bebidas no alcohólicas sin gasificar-refrescos"],
      "unidad_medida": ["Litros", "Litros"],
      "ventas_cantidad": [7329764148, 1979135546],
      "Inventario_cantidad_31_dic": [234404972, 44604232]
    }
}

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
    'agua':355118, # No se fabricará
    'gaseosa': 194593,
    'concentrada':2987,
    'jugos':59985,
    'cafe': 5737, # No se fabricará
    'te': 36592, # No se fabricará
    'energeticas': 20974,
    'deportivas': 16515
}

df_share = pd.DataFrame(share_productos.items(), columns=['bebida', 'ventas'])
df_share['share'] = df_share['ventas'] / df_share['ventas'].sum()
bebidas_a_eliminar = ['agua', 'cafe', 'te'] # remover las que no se fabrican
df_share = df_share[~df_share['bebida'].isin(bebidas_a_eliminar)]

df_EMMET_2024['ventas_proporcion'] = df_EMMET_2024['ventas_reales'] / df_EMMET_2024['ventas_reales'].sum()

# Inventario total al 31 de dic 2023
I_final_2023 = df_EAM_2023["Inventario_cantidad_31_dic"].sum()

# Índice promedio y de enero 2024 (EMMET)
promedio_prod = df_EMMET_2024["produccion_real"].mean()
enero_prod = df_EMMET_2024.loc[df_EMMET_2024["mes"] == 1, "produccion_real"].values[0]

# Inventario inicial estimado (enero 2024)
I_inicial_estimado = I_final_2023 * (enero_prod / promedio_prod)

# Ajuste por participación del 1%
I_inicial_1pct = I_inicial_estimado * 0.002

# Distribuir por share de bebidas
df_inventario_inicial = df_share.copy()
df_inventario_inicial["inventario_inicial"] = df_inventario_inicial["share"] * I_inicial_1pct

def generar_demanda_sarima(EAM_data = EAM_data, df_EMMET_2024 = df_EMMET_2024, df_share = df_share, n_periodos = 3):
    resultados = []

    # --- Construir datos históricos ---
    for anio, datos in EAM_data.items():
        ventas_totales_anio = sum(datos['ventas_cantidad'])
        df_mensual = pd.DataFrame({
            'mes': df_EMMET_2024['mes'],
            'ventas_mes_total': df_EMMET_2024['ventas_proporcion'] * (ventas_totales_anio/12)
        })

        for _, row_prod in df_share.iterrows():
            for _, row_mes in df_mensual.iterrows():
                demanda = row_mes['ventas_mes_total'] * row_prod['share'] * 0.01
                resultados.append({
                    'anio': anio,
                    'mes': int(row_mes['mes']),
                    'bebida': row_prod['bebida'],
                    'demanda_esperada': demanda
                })

    df_demanda = pd.DataFrame(resultados)

    df_final = []
    for bebida in df_share['bebida']:
        df_b = df_demanda[df_demanda['bebida'] == bebida].copy()
        df_b['fecha'] = pd.to_datetime(df_b['anio'].astype(str) + '-' + df_b['mes'].astype(str) + '-01')
        df_b.set_index('fecha', inplace=True)
        ts = df_b['demanda_esperada'].asfreq('MS')

        # Ajustar SARIMA para capturar tendencia y estacionalidad mensual
        model = SARIMAX(ts,
                        order=(1,1,1),
                        seasonal_order=(1,1,1,12),
                        enforce_stationarity=False,
                        enforce_invertibility=False)
        model_fit = model.fit(disp=False)

        forecast = model_fit.get_forecast(steps=n_periodos)
        df_forecast = pd.DataFrame({
            'fecha': forecast.predicted_mean.index,
            'demanda_esperada': forecast.predicted_mean.values,
            'bebida': bebida
        })

        df_hist_y_forecast = pd.concat([df_b.reset_index()[['fecha','demanda_esperada']], df_forecast], ignore_index=True)
        df_hist_y_forecast['anio'] = df_hist_y_forecast['fecha'].dt.year
        df_hist_y_forecast['mes'] = df_hist_y_forecast['fecha'].dt.month
        df_hist_y_forecast['bebida'] = bebida

        df_final.append(df_hist_y_forecast[['anio','mes','bebida','demanda_esperada']])

    df_result = pd.concat(df_final, ignore_index=True)
    df_result = df_result.drop_duplicates(subset=['anio','mes','bebida'])
    df_result = df_result.sort_values(['anio','mes','bebida']).reset_index(drop=True).round(2)

    return df_result

def graficar_demanda_interactivo(df_demanda_esperada, anio_inicio=None, anio_fin=None, escala=1000, fecha_max_hist=pd.Timestamp('2024-01-01')):
    """
    Grafica la demanda mensual por bebida de manera interactiva usando Plotly.

    Args:
        df_demanda_esperada (pd.DataFrame): columnas ['anio','mes','bebida','demanda_esperada']
        anio_inicio (int, optional): Año inicial a mostrar. Por defecto, primer año disponible.
        anio_fin (int, optional): Año final a mostrar. Por defecto, último año disponible.
        escala (float, optional): Factor de escala para el eje Y. Ej: 1000 para miles.
        fecha_max_hist (pd.Timestamp, optional): Fecha máxima que se considera histórico.
                                                 Por defecto, última fecha - 12 meses.
    """
    # Crear columna de fecha
    df_demanda_esperada = df_demanda_esperada.copy()
    df_demanda_esperada['fecha'] = pd.to_datetime(df_demanda_esperada['anio'].astype(str) + '-' +
                                                  df_demanda_esperada['mes'].astype(str) + '-01')

    # Límites por defecto
    if anio_inicio is None:
        anio_inicio = df_demanda_esperada['anio'].min()
    if anio_fin is None:
        anio_fin = df_demanda_esperada['anio'].max()

    df_plot = df_demanda_esperada[(df_demanda_esperada['anio'] >= anio_inicio) &
                                  (df_demanda_esperada['anio'] <= anio_fin)].copy()

    # Fecha máxima histórica
    if fecha_max_hist is None:
        fecha_max_hist = df_plot['fecha'].max() - pd.DateOffset(months=12)

    fig = go.Figure()

    colores = qualitative.Plotly
    bebidas = df_plot['bebida'].unique()

    for i, bebida in enumerate(bebidas):
        color = colores[i % len(colores)]
        df_bebida = df_plot[df_plot['bebida'] == bebida].sort_values('fecha')

        # Histórico atenuado (sin leyenda)
        df_hist = df_bebida[df_bebida['fecha'] <= fecha_max_hist]
        if not df_hist.empty:
            fig.add_trace(go.Scatter(
                x=df_hist['fecha'][:-1],
                y=df_hist['demanda_esperada']/escala,
                mode='lines',
                line=dict(color=color, width=2, dash='solid'),
                showlegend=False,
                hovertemplate="%{text}<br>%{x|%b-%Y}<br>%{y:.2f}k L<extra></extra>",
                text=df_hist['bebida']
            ))

        # Pronóstico (con leyenda)
        df_forecast = df_bebida[df_bebida['fecha'] >= fecha_max_hist]
        if not df_forecast.empty:
            # Conectar último histórico con primer pronóstico
            if not df_hist.empty:
                df_forecast_plot = pd.concat([df_hist.iloc[[-2]],df_hist.iloc[[-1]], df_forecast])
            else:
                df_forecast_plot = df_forecast

            fig.add_trace(go.Scatter(
                x=df_forecast_plot['fecha'],
                y=df_forecast_plot['demanda_esperada']/escala,
                mode='lines+markers',
                line=dict(color=color, width=2, dash='dot'),
                marker=dict(size=6),
                name=bebida,
                showlegend=True,
                hovertemplate="%{text}<br>%{x|%b-%Y}<br>%{y:.2f}k L<extra></extra>",
                text=df_forecast_plot['bebida']
            ))

    fig.update_layout(
        title=dict(
          text='📊 Pronóstico de Demanda e Históricos',
          x=0.5,
          xanchor='center',
          yanchor='top',
          font=dict(family='Arial, sans-serif', size=24, color='darkblue')
        ),
        xaxis_title='Mes-Año',
        yaxis_title=f'Demanda esperada (x{escala} litros)',
        xaxis=dict(showgrid=True, gridcolor='lightgrey'),
        yaxis=dict(showgrid=True, gridcolor='lightgrey', zeroline=False),
        template='plotly_white',
        legend=dict(title='Pronósticos', orientation='h', yanchor='bottom', y=-0.2, xanchor='right', x=1),
        hovermode='closest',
        margin=dict(l=60, r=20, t=100, b=60),
        width=1100,
        height=700
    )

    return fig

def inventario_inicial():
    # Inventario total al 31 de dic 2023
    I_final_2023 = df_EAM_2023["Inventario_cantidad_31_dic"].sum()

    # Índice promedio y de enero 2024 (EMMET)
    promedio_prod = df_EMMET_2024["produccion_real"].mean()
    enero_prod = df_EMMET_2024.loc[df_EMMET_2024["mes"] == 1, "produccion_real"].values[0]

    # Inventario inicial estimado (enero 2024)
    I_inicial_estimado = I_final_2023 * (enero_prod / promedio_prod)

    # Ajuste por participación del 1%
    I_inicial_1pct = I_inicial_estimado * 0.002

    # Distribuir por share de bebidas
    df_inventario_inicial = df_share.copy()
    df_inventario_inicial["inventario_inicial"] = df_inventario_inicial["share"] * I_inicial_1pct
    
    return df_inventario_inicial