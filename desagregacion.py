import pandas as pd
from pulp import *
import plotly.graph_objects as go


def calcular_demanda_neta(df_resultado):
    """
    Calcula la demanda neta (demanda no cubierta por inventarios iniciales o previos).
    Si el inventario supera la demanda del periodo, el excedente se arrastra al siguiente.
    """
    df = df_resultado.copy().fillna(0)
    df_neta = []

    for bebida, subdf in df.groupby('bebida'):
        subdf = subdf.sort_values('mes').reset_index(drop=True)
        inventario_carry = subdf.loc[0, 'inventario_inicial'] or 0
        neta = []

        for _, row in subdf.iterrows():
            demanda = row['demanda']
            demanda_neta = max(demanda - inventario_carry, 0)
            neta.append(demanda_neta)
            # actualizar carry para el siguiente periodo
            inventario_carry = max(inventario_carry - demanda, 0) + row['inventario_final']

        subdf['demanda_neta'] = neta
        df_neta.append(subdf)

    return pd.concat(df_neta, ignore_index=True)


def desagregar_produccion(demanda_df, df_inventario_inicial, resultados, num_per, cost_inv = 1, cost_prod=1):
    # Calcular mes continuo
    df_demanda_mensual = demanda_df.iloc[-num_per*5:]
    anio_base = df_demanda_mensual['anio'].min()
    df_demanda_mensual = df_demanda_mensual.assign(
        mes_continuo=lambda x: (x['anio'] - anio_base) * 12 + x['mes']
    )

    # Diccionario (bebida, mes_continuo) → demanda
    demanda_dict = (
        df_demanda_mensual[['bebida', 'mes_continuo', 'demanda_esperada']]
        .set_index(['bebida', 'mes_continuo'])['demanda_esperada']
        .to_dict()
    )
    productos = sorted({i for i, _ in demanda_dict.keys()})
    periodos = sorted({t for _, t in demanda_dict.keys()})

    # Inventarios iniciales
    inv_inicial = df_inventario_inicial.set_index('bebida')['inventario_inicial'].to_dict()
    # Producción total por periodo
    prod_t = resultados[['Periodo', 'Producción']].set_index('Periodo')['Producción'].to_dict()

    t0 = min(periodos)
    I0 = {i: inv_inicial.get(i, 0.0) for i in productos}

    # Modelo
    modelo = LpProblem("Desagregacion_Multilineas_SinFaltantes", LpMinimize)
    x = LpVariable.dicts("produccion", (productos, periodos), lowBound=0)
    I = LpVariable.dicts("inventario", (productos, periodos), lowBound=0)
    modelo += lpSum(cost_inv*I[i][t] + cost_prod*x[i][t] for i in productos for t in periodos)

    for i in productos:
        for t in periodos:
            demanda = demanda_dict.get((i, t), 0.0)
            if t == t0:
                modelo += I[i][t] == I0[i] + x[i][t] - demanda
            else:
                modelo += I[i][t] == I[i][t-1] + x[i][t] - demanda

    for t in periodos:
        if t in prod_t:
            modelo += lpSum(x[i][t] for i in productos) == prod_t[t]

    modelo.solve()

    # DataFrame de resultados
    # DataFrame de resultados base
    df_resultado = pd.DataFrame([
        {
            'mes': t,
            'bebida': i,
            'demanda': round(demanda_dict.get((i, t), 0.0), 2),
            'produccion_asignada': round(max(x[i][t].value(), 0), 2),
            'inventario_final': round(max(I[i][t].value(), 0), 2)
        }
        for i in productos for t in periodos
    ])

    # Añadir inventario inicial = inventario final del mes anterior (o I0 si es el primero)
    df_resultado['inventario_inicial'] = df_resultado.apply(
        lambda row: I0[row['bebida']] if row['mes'] == t0 else None,
        axis=1
    )

    for bebida in productos:
        subdf = df_resultado[df_resultado['bebida'] == bebida].sort_values('mes')
        subdf.loc[subdf['mes'] > t0, 'inventario_inicial'] = subdf['inventario_final'].shift(1)
        df_resultado.loc[subdf.index, 'inventario_inicial'] = subdf['inventario_inicial']


    # Calcular demanda neta
    df_resultado = calcular_demanda_neta(df_resultado)

    # Pivoteos
    df_prod = df_resultado.pivot(index='mes', columns='bebida', values='produccion_asignada').reset_index().fillna(0)
    df_inv = df_resultado.pivot(index='mes', columns='bebida', values='inventario_inicial').reset_index().fillna(0)
    df_dem_neta = df_resultado.pivot(index='mes', columns='bebida', values='demanda').reset_index().fillna(0)

    # Figura interactiva
        # Figura interactiva
    fig = go.Figure()
    for bebida in productos:
        # Producción
        fig.add_trace(go.Bar(
            x=df_prod['mes'],
            y=df_prod[bebida],
            name=f'Producción {bebida}',
            visible=False,
            marker_color='lightblue'
        ))

        # Inventario (ahora también en barras)
        fig.add_trace(go.Bar(
            x=df_inv['mes'],
            y=df_inv[bebida],
            name=f'Inventario {bebida}',
            visible=False,
            marker_color='orange',
            opacity=0.8
        ))

        # Demanda neta (línea)
        fig.add_trace(go.Scatter(
            x=df_dem_neta['mes'],
            y=df_dem_neta[bebida],
            mode='lines+markers',
            name=f'Demanda {bebida}',
            visible=False,
            line=dict(width=3, color='green')
        ))

    # Mostrar por defecto el primer producto
    if productos:
        fig.data[0].visible = True
        fig.data[1].visible = True
        fig.data[2].visible = True

    # Botones de selección
    # Botones de selección
    buttons = []
    for i, bebida in enumerate(productos):
        visible = [False] * len(fig.data)
        visible[3*i] = True      # Producción
        visible[3*i+1] = True    # Inventario
        visible[3*i+2] = True    # Demanda neta
        buttons.append(dict(
            label=bebida,
            method='update',
            args=[
                {'visible': visible},
                {'title.text': f'Producción + Inventario vs Demanda (Litros) - {productos[0]} (Costo óptimo: ${value(modelo.objective):,.0f})'}
            ]
        ))


    fig.update_layout(
        title={
            'text': f'Producción + Inventario vs Demanda (Litros) - {productos[0]} (Costo óptimo: ${value(modelo.objective):,.0f})',
            'x': 0.5,
            'y': 0.95,          
            'xanchor': 'center',
            'yanchor': 'top'
        },
        updatemenus=[dict(
            active=0,
            buttons=buttons,
            x=0.85,
            y=0.95,              
            xanchor='right',
            yanchor='top'
        )],
        xaxis=dict(title='Mes', tickvals=df_prod['mes']),
        yaxis=dict(title='Litros'),
        template='plotly_white',
        height=600,
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0.01),
        barmode='stack'
    )

    return df_prod, df_inv, df_resultado, fig


def grafica_consolidada(df_prod, df_inv, df_resultado, productos, litros_por_unidad=0.5, lote=100):
    """
    Gráfica consolidada (en lotes):
    Muestra Producción e Inventario apilados y la Demanda total como línea superior.
    """
    # --- Extraer demanda total ---
    df_dem_total = df_resultado.pivot(index='mes', columns='bebida', values='demanda').reset_index().fillna(0)

    # --- Copias limpias ---
    df_prod_units = df_prod.copy().fillna(0)
    df_inv_units = df_inv.copy().fillna(0)
    df_dem_units = df_dem_total.copy().fillna(0)

    # --- Conversión a lotes ---
    for bebida in productos:
        df_prod_units[bebida] = (df_prod_units[bebida] / litros_por_unidad) / lote
        df_inv_units[bebida] = (df_inv_units[bebida] / litros_por_unidad) / lote
        df_dem_units[bebida] = (df_dem_units[bebida] / litros_por_unidad) / lote

    # === FIGURA ===
    fig = go.Figure()

    for bebida in productos:
        # Inventario
        fig.add_trace(go.Bar(
            x=df_inv_units['mes'],
            y=df_inv_units[bebida],
            name=f'Inventario {bebida}',
            visible=False,
            marker=dict(color='rgba(255, 167, 38, 0.85)', line=dict(color='rgba(255, 143, 0, 1)', width=1.2)),
            hovertemplate='Inventario: %{y:.1f} lotes<extra></extra>'
        ))

        # Producción
        fig.add_trace(go.Bar(
            x=df_prod_units['mes'],
            y=df_prod_units[bebida],
            name=f'Producción {bebida}',
            visible=False,
            marker=dict(color='rgba(66, 165, 245, 0.9)', line=dict(color='rgba(25, 118, 210, 1)', width=1.2)),
            hovertemplate='Producción: %{y:.1f} lotes<extra></extra>'
        ))

        # Demanda total
        fig.add_trace(go.Scatter(
            x=df_dem_units['mes'],
            y=df_dem_units[bebida],
            mode='lines+markers',
            name=f'Demanda total {bebida}',
            visible=False,
            line=dict(width=4, color='rgba(0,150,100,1)', shape='spline'),
            marker=dict(size=8, color='rgba(0,120,80,1)', line=dict(width=1, color='white')),
            hovertemplate='Demanda total: %{y:.1f} lotes<extra></extra>'
        ))

    # Mostrar primer producto por defecto
    if productos:
        fig.data[0].visible = True
        fig.data[1].visible = True
        fig.data[2].visible = True

    # --- Botones interactivos ---
    buttons = []
    for i, bebida in enumerate(productos):
        visible = [False] * len(fig.data)
        visible[3*i:3*i+3] = [True, True, True]
        buttons.append(dict(
            label=bebida,
            method='update',
            args=[{'visible': visible}]  # NOTA: el título **no cambia**
        ))

    # --- Layout final ---
    fig.update_layout(
        updatemenus=[dict(
            active=0,
            buttons=buttons,
            x=0.85,
            y=1.02,          # casi a la altura del título
            xanchor='right',
            yanchor='bottom',  # mide desde la base del botón
            bgcolor='rgba(245,245,245,0.9)',
            bordercolor='lightgray',
            borderwidth=1
        )],
        xaxis=dict(
            title='Mes',
            tickmode='array',
            tickvals=df_prod_units['mes'],
            ticktext=[str(m) for m in df_prod_units['mes']]
        ),
        yaxis=dict(title=f'Volumen (lotes de {lote} por {litros_por_unidad} L/und)'),
        title={
            'text': f'📦 Producción, Inventario y Demanda Total (en lotes)',
            'x': 0.5,
            'y': 0.95,
            'xanchor': 'center',
            'yanchor': 'top'
        },
        template='plotly_white',
        height=620,
        hovermode='x unified',
        legend=dict(
            y=-0.18, x=0.5, xanchor='center', yanchor='bottom',
            orientation='h', bgcolor='rgba(255,255,255,0.8)'
        ),
        barmode='stack',
        plot_bgcolor='rgba(250,250,250,1)',
        paper_bgcolor='rgba(255,255,255,1)',
        font=dict(family='Arial', size=13, color='#333')
    )

    return fig


