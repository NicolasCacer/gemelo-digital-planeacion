# simulacion.py

import simpy
import random
import pandas as pd

def simular_flowshop(produccion_diaria: pd.DataFrame,
                     tiempo_mezcla: int,
                     tiempo_pasteurizacion: int,
                     tiempo_llenado: int,
                     tiempo_etiquetado: int,
                     tiempo_almacenamiento: int) -> list:
    """
    Simula un flowshop para la producción diaria usando SimPy.
    
    Args:
        produccion_diaria: DataFrame con columnas 'Mes' y 'Produccion_diaria'.
        tiempo_mezcla: Tiempo de mezcla por lote (minutos).
        tiempo_pasteurizacion: Tiempo de pasteurización por lote (minutos).
        tiempo_llenado: Tiempo de llenado por lote (minutos).
        tiempo_etiquetado: Tiempo de etiquetado por lote (minutos).
        tiempo_almacenamiento: Tiempo de almacenamiento por lote (horas).
        
    Returns:
        WIP_log: Lista con tiempos de ciclo de cada lote (minutos).
    """
    env = simpy.Environment()
    WIP_log = []

    def lote(env, mes, id_lote):
        start = env.now
        yield env.timeout(random.randint(tiempo_mezcla-5, tiempo_mezcla+5))
        yield env.timeout(random.randint(tiempo_pasteurizacion-5, tiempo_pasteurizacion+5))
        yield env.timeout(random.randint(tiempo_llenado-2, tiempo_llenado+2))
        yield env.timeout(random.randint(tiempo_etiquetado-5, tiempo_etiquetado+5))
        WIP_log.append(env.now - start)
        yield env.timeout(tiempo_almacenamiento*60)  # convertir horas a minutos

    for i, mes in enumerate(produccion_diaria['Mes']):
        for lote_id in range(int(produccion_diaria['Produccion_diaria'][i])):
            env.process(lote(env, mes, lote_id+1))

    env.run()
    return WIP_log
