import pandas as pd
from pulp import *
import plotly.graph_objects as go

def desagregar_produccion(demanda_df, df_inventario_inicial, resultados, num_per):
    # Calcular el mes continuo
    df_demanda_mensual = demanda_df.iloc[-num_per*5:]
    anio_base = df_demanda_mensual['anio'].min()
    df_demanda_mensual = df_demanda_mensual.assign(
        mes_continuo=lambda x: (x['anio'] - anio_base) * 12 + x['mes']
    )

    # Crear diccionario (bebida, mes_continuo) -> demanda
    demanda_dict = (
        df_demanda_mensual[['bebida', 'mes_continuo', 'demanda_esperada']]
        .set_index(['bebida', 'mes_continuo'])['demanda_esperada']
        .to_dict()
    )
    productos = sorted({i for i, _ in demanda_dict.keys()})
    periodos = sorted({t for _, t in demanda_dict.keys()})
    
    inv_inicial = df_inventario_inicial.set_index('bebida')['inventario_inicial'].to_dict()
    prod_t = resultados[['Periodo','Producción']].set_index('Periodo')['Producción'].to_dict()

    t0 = min(periodos)
    I0 = {i: inv_inicial.get(i, 0.0) for i in productos}

    # Modelo
    modelo = LpProblem("Desagregacion_Multilineas_SinFaltantes", LpMinimize)
    x = LpVariable.dicts("produccion", (productos, periodos), lowBound=0)
    I = LpVariable.dicts("inventario", (productos, periodos), lowBound=0)
    modelo += lpSum(I[i][t] + x[i][t] for i in productos for t in periodos)

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

    modelo.solve(pulp.PULP_CBC_CMD(msg=False))

    # Crear DataFrame
    df_resultado = pd.DataFrame([
        {
            'mes': t,
            'bebida': i,
            'inventario_inicial': round(I0[i], 2) if t==t0 else None,
            'demanda': round(demanda_dict.get((i, t), 0.0), 2),
            'produccion_asignada': round(max(x[i][t].value(), 0), 2),
            'inventario_final': round(max(I[i][t].value(), 0), 2)
        }
        for i in productos for t in periodos
    ])
    df_prod = df_resultado.pivot(index='mes', columns='bebida', values='produccion_asignada').reset_index()
    df_inv = df_resultado.pivot(index='mes', columns='bebida', values='inventario_final').reset_index()

    # Crear figura
    fig = go.Figure()
    for bebida in productos:
        fig.add_trace(go.Bar(x=df_prod['mes'], y=df_prod[bebida], name=f'Producción {bebida}', visible=False))
        fig.add_trace(go.Scatter(x=df_inv['mes'], y=df_inv[bebida], mode='lines+markers',
                                 name=f'Inventario {bebida}', line=dict(width=3, dash='dash'), visible=False))

    if productos:
        fig.data[0].visible = True
        fig.data[1].visible = True

    # Botones para seleccionar bebida y mantener título
    buttons = []
    for i, bebida in enumerate(productos):
        visible = [False] * len(fig.data)
        visible[2*i] = True
        visible[2*i+1] = True
        buttons.append(dict(
            label=bebida,
            method='update',
            args=[
                {'visible': visible},
                {'title': {'text': f'Planeación de Producción e Inventario - {bebida}'}}
            ]
        ))

    fig.update_layout(
        title={'text': f'Planeación de Producción e Inventario (Litros) - {productos[0]}' if productos else 'No hay productos'},
        xaxis=dict(title='Mes', tickmode='array', tickvals=df_prod['mes'], ticktext=df_prod['mes']),
        yaxis_title='Litros',
        template='plotly_white',
        height=600,
        updatemenus=[dict(active=0, buttons=buttons, x=0.85, y=1.15, xanchor='right', yanchor='top')]
    )

    return df_prod, df_inv, df_resultado, fig



def grafica_consolidada(df_prod, df_inv, df_resultado, productos):
    import plotly.graph_objects as go

    # Supuesto: 0.5 litros por unidad
    litros_por_unidad = 0.5

    # Convertir a unidades
    df_prod_units = df_prod.copy()
    df_inv_units = df_inv.copy()
    df_demanda_units = df_resultado.pivot(index='mes', columns='bebida', values='demanda').reset_index()

    for bebida in productos:
        df_prod_units[bebida] = df_prod_units[bebida] / litros_por_unidad
        df_inv_units[bebida] = df_inv_units[bebida] / litros_por_unidad
        df_demanda_units[bebida] = df_demanda_units[bebida] / litros_por_unidad

    # Crear figura
    fig = go.Figure()

    # Añadir trazas para todas las bebidas
    for bebida in productos:
        # Producción
        fig.add_trace(
            go.Bar(
                x=df_prod_units['mes'],
                y=df_prod_units[bebida],
                name=f'Producción bebida {bebida}',
                visible=False,
                marker_color='lightblue'
            )
        )
        # Inventario
        fig.add_trace(
            go.Scatter(
                x=df_inv_units['mes'],
                y=df_inv_units[bebida],
                mode='lines+markers',
                name=f'Inventario bebida {bebida}',
                line=dict(width=3, dash='dash', color='orange'),
                visible=False
            )
        )
        # Demanda
        fig.add_trace(
            go.Scatter(
                x=df_demanda_units['mes'],
                y=df_demanda_units[bebida],
                mode='lines',
                name=f'Demanda bebida {bebida}',
                line=dict(width=3, color='green'),
                visible=False
            )
        )

    # Hacer la primera bebida visible por defecto
    if productos:
        fig.data[0].visible = True
        fig.data[1].visible = True
        fig.data[2].visible = True

    # Botones para seleccionar bebida
    buttons = []
    for i, bebida in enumerate(productos):
        visible = [False] * len(fig.data)
        visible[3*i] = True
        visible[3*i+1] = True
        visible[3*i+2] = True
        buttons.append(dict(
            label=bebida,
            method='update',
            args=[
                {'visible': visible},
                {'title': {'text': f'Demanda, Planeación de Producción e Inventario - {bebida}<br><sup>Supuesto: 1 unidad = 0.5 litros</sup>'}}
            ]
        ))

    # Layout
    fig.update_layout(
        updatemenus=[dict(
            active=0,
            buttons=buttons,
            x=0.85,
            y=1.2,
            xanchor='right',
            yanchor='top'
        )],
        title= {
            'text': f"Demanda, Planeación de Producción e Inventario (unidades)- {productos[0]}<br><sup>Supuesto: 1 unidad = 0.5 litros</sup>",
            'x': 0.5,
            'xanchor': 'center'  # centrar el título
        },
        xaxis=dict(
            title='Mes',
            tickmode='array',
            tickvals=df_prod_units['mes'],
            ticktext=df_prod_units['mes']
        ),
        yaxis_title='Unidades de producto',
        template='plotly_white',
        height=600,
        legend=dict(
            y=-0.2,
            x=0.5,
            xanchor='center',
            yanchor='bottom',
            orientation='h'
        )
    )

    return fig
