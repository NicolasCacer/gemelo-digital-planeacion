# simulacion_dashboard.py

import simpy
import random
import pandas as pd

def simular_flowshop_dashboard(df_desagregado: pd.DataFrame,
                                tiempo_mezcla: int = 60,
                                tiempo_pasteurizacion: int = 120,
                                tiempo_llenado: int = 30,
                                tiempo_etiquetado: int = 20,
                                tiempo_almacenamiento: int = 24) -> pd.DataFrame:
    """
    Simula un flowshop de producción mensual usando SimPy, a partir de los datos del dashboard.
    
    Args:
        df_desagregado: DataFrame con columnas 'Mes', 'Produccion_mes' y 'Tiempo_inicio_mes'.
        tiempo_mezcla: Tiempo de mezcla por lote (minutos)
        tiempo_pasteurizacion: Tiempo de pasteurización por lote (minutos)
        tiempo_llenado: Tiempo de llenado por lote (minutos)
        tiempo_etiquetado: Tiempo de etiquetado por lote (minutos)
        tiempo_almacenamiento: Tiempo de almacenamiento por lote (horas)
        
    Returns:
        df_WIP: DataFrame con registro de cada lote:
            - 'Mes'
            - 'Lote'
            - 'Tiempo_inicio_simulado' (minutos desde inicio de simulación)
            - 'Tiempo_ciclo' (minutos hasta finalizar almacenamiento)
    """
    
    env = simpy.Environment()
    WIP_log = []

    def lote(env, mes, id_lote):
        start = env.now
        # Simulación con pequeña variabilidad
        yield env.timeout(random.randint(tiempo_mezcla-5, tiempo_mezcla+5))
        yield env.timeout(random.randint(tiempo_pasteurizacion-5, tiempo_pasteurizacion+5))
        yield env.timeout(random.randint(tiempo_llenado-2, tiempo_llenado+2))
        yield env.timeout(random.randint(tiempo_etiquetado-5, tiempo_etiquetado+5))
        # Registro del tiempo de ciclo
        tiempo_ciclo = env.now - start
        WIP_log.append({
            'Mes': mes,
            'Lote': id_lote,
            'Tiempo_inicio_simulado': start,
            'Tiempo_ciclo': tiempo_ciclo
        })
        # Tiempo de almacenamiento
        yield env.timeout(tiempo_almacenamiento * 60)  # convertir horas a minutos

    # Crear procesos por lote según la producción mensual
    for i, row in df_desagregado.iterrows():
        mes = row['Mes']
        cantidad_lotes = int(row['Produccion_mes'])
        for lote_id in range(1, cantidad_lotes+1):
            # Podemos iniciar cada mes en el tiempo de inicio simulado (en meses convertido a minutos)
            tiempo_inicio_mes = row['Tiempo_inicio_mes'] * 30 * 24 * 60  # 30 días * 24 h * 60 min
            env.process(lote(env, mes, lote_id))
            # Nota: si se desea escalonar por lote dentro del mes, se puede agregar yield env.timeout(...) aquí

    env.run()# simulacion_dashboard_optimizada.py

import simpy
import pandas as pd

def simular_flowshop_dashboard_optimizado(df_desagregado: pd.DataFrame,
                                           tiempo_mezcla: int = 60,
                                           tiempo_pasteurizacion: int = 120,
                                           tiempo_llenado: int = 30,
                                           tiempo_etiquetado: int = 20,
                                           tiempo_almacenamiento: int = 24) -> pd.DataFrame:
    """
    Simula un flowshop por mes de forma optimizada, evitando crear un proceso por lote.
    
    df_desagregado: DataFrame con columnas 'Mes', 'Produccion_mes', 'Tiempo_inicio_mes'.
    Tiempos en minutos, almacenamiento en horas.
    
    Retorna df_WIP con:
        - Mes
        - Tiempo_inicio_simulado (inicio del mes en la simulación)
        - Tiempo_produccion_total (minutos para producir todo el mes incluyendo todas las estaciones)
        - Tiempo_ciclo_total (minutos hasta finalizar almacenamiento)
    """
    env = simpy.Environment()
    WIP_log = []

    def producir_mes(env, mes, produccion_mes, tiempo_inicio_mes):
        start = tiempo_inicio_mes
        env.now = start  # Ajustar el tiempo de inicio del mes
        
        # Tiempo total de producción = sumatoria de tiempos por lote * cantidad de lotes
        tiempo_total_produccion = produccion_mes * (tiempo_mezcla + tiempo_pasteurizacion +
                                                    tiempo_llenado + tiempo_etiquetado)
        
        # Variación opcional: +-5% del tiempo total
        variacion = tiempo_total_produccion * 0.05
        tiempo_total_produccion = tiempo_total_produccion * (1 + 0.0)  # o random.uniform(-0.05,0.05)
        
        yield env.timeout(tiempo_total_produccion)
        
        tiempo_ciclo_total = tiempo_total_produccion + tiempo_almacenamiento*60
        WIP_log.append({
            'Mes': mes,
            'Tiempo_inicio_simulado': start,
            'Tiempo_produccion_total': tiempo_total_produccion,
            'Tiempo_ciclo_total': tiempo_ciclo_total
        })
        
        # Avanzar env al final del almacenamiento
        yield env.timeout(tiempo_almacenamiento*60)

    # Crear procesos por mes
    for i, row in df_desagregado.iterrows():
        mes = row['Mes']
        produccion_mes = row['Produccion_mes']
        tiempo_inicio_mes = row['Tiempo_inicio_mes'] * 30 * 24 * 60  # convertir meses a minutos
        env.process(producir_mes(env, mes, produccion_mes, tiempo_inicio_mes))

    env.run()
    
    df_WIP = pd.DataFrame(WIP_log)
    return df_WIP

    
    df_WIP = pd.DataFrame(WIP_log)
    return df_WIP
