def simular_produccion(num_lotes=10, tamano_lote_max=100,
                       num_mezcla=2, num_pasteurizacion=2, num_llenado=2,
                       num_etiquetado=2, num_camaras=1):
    
    import simpy, random, pandas as pd

    # ----- Datos de simulación -----
    MEZCLA_TIEMPO = (15, 25)
    PASTEURIZACION_TIEMPO = (30, 45)
    LLENADO_TIEMPO_POR_100 = (10, 15)
    ETIQUETADO_TIEMPO = (20, 20)
    ALMACENAMIENTO_MAX = 48*60

    resultados = []
    uso_mezcla, uso_pasteur, uso_llenado, uso_etiquetado, uso_camara = [], [], [], [], []

    # ----- Funciones internas -----
    def registrar_uso(env, recurso, lista_uso, evento):
        lista_uso.append((env.now, recurso.count, len(recurso.queue), evento))

    def lote_proceso(env, nombre, mezcla, pasteurizacion, llenado, etiquetado, camara):
        inicio = env.now
        tamano_lote = tamano_lote_max
        # Mezcla
        with mezcla.request() as req:
            yield req
            registrar_uso(env, mezcla, uso_mezcla, "INICIO")
            yield env.timeout(random.randint(*MEZCLA_TIEMPO))
            registrar_uso(env, mezcla, uso_mezcla, "FIN")
        # Pasteurización
        with pasteurizacion.request() as req:
            yield req
            registrar_uso(env, pasteurizacion, uso_pasteur, "INICIO")
            yield env.timeout(random.randint(*PASTEURIZACION_TIEMPO))
            registrar_uso(env, pasteurizacion, uso_pasteur, "FIN")
        # Llenado
        with llenado.request() as req:
            yield req
            registrar_uso(env, llenado, uso_llenado, "INICIO")
            factor = tamano_lote/100
            yield env.timeout(random.randint(*LLENADO_TIEMPO_POR_100)*factor)
            registrar_uso(env, llenado, uso_llenado, "FIN")
        # Etiquetado
        with etiquetado.request() as req:
            yield req
            registrar_uso(env, etiquetado, uso_etiquetado, "INICIO")
            yield env.timeout(random.randint(*ETIQUETADO_TIEMPO))
            registrar_uso(env, etiquetado, uso_etiquetado, "FIN")
        # Almacenamiento
        with camara.request() as req:
            yield req
            registrar_uso(env, camara, uso_camara, "INICIO")
            tiempo_almacenamiento = random.randint(0, ALMACENAMIENTO_MAX)
            yield env.timeout(tiempo_almacenamiento)
            registrar_uso(env, camara, uso_camara, "FIN")
        fin = env.now
        resultados.append({
            'Lote': nombre,
            'Tamano_botellas': tamano_lote,
            'Inicio': inicio,
            'Fin': fin,
            'Tiempo_total': fin-inicio,
            'Tiempo_almacenamiento': tiempo_almacenamiento
        })

    def generar_lotes(env):
        for i in range(1, num_lotes+1):
            yield env.timeout(random.randint(0,30))
            env.process(lote_proceso(env, f"L{i}", mezcla, pasteurizacion, llenado, etiquetado, camara))

    def calcular_utilizacion(uso, tiempo_total_sim):
        if not uso: return 0,0,0
        df = pd.DataFrame(uso, columns=['Tiempo','Ocupados','En_cola','Evento']).sort_values('Tiempo')
        ocupados_area = sum((df.loc[i+1,'Tiempo']-df.loc[i,'Tiempo'])*df.loc[i,'Ocupados'] for i in range(len(df)-1))
        cola_area = sum((df.loc[i+1,'Tiempo']-df.loc[i,'Tiempo'])*df.loc[i,'En_cola'] for i in range(len(df)-1))
        return ocupados_area/tiempo_total_sim, cola_area/tiempo_total_sim, df['En_cola'].max()

    # ----- Configuración SimPy -----
    env = simpy.Environment()
    mezcla = simpy.Resource(env, capacity=num_mezcla)
    pasteurizacion = simpy.Resource(env, capacity=num_pasteurizacion)
    llenado = simpy.Resource(env, capacity=num_llenado)
    etiquetado = simpy.Resource(env, capacity=num_etiquetado)
    camara = simpy.Resource(env, capacity=num_camaras)

    env.process(generar_lotes(env))
    env.run()

    df_resultados = pd.DataFrame(resultados)
    tiempo_total_sim = df_resultados['Fin'].max()
    
    # Métricas por recurso
    recursos = {'Mezcla': uso_mezcla, 'Pasteurizacion': uso_pasteur, 'Llenado': uso_llenado,
                'Etiquetado': uso_etiquetado, 'Camara': uso_camara}
    lista_utilizacion = []
    for nombre, uso in recursos.items():
        util, cola, max_cola = calcular_utilizacion(uso, tiempo_total_sim)
        lista_utilizacion.append({
            'Recurso': nombre,
            'Utilizacion': util,
            'Cola_promedio': cola,
            'Cola_maxima': max_cola
        })
    df_utilizacion = pd.DataFrame(lista_utilizacion)
    
    # Métricas globales
    wip = df_resultados['Tiempo_total'].sum()/tiempo_total_sim
    cycle_time = df_resultados['Tiempo_total'].mean()
    throughput = len(df_resultados)/tiempo_total_sim
    takt_time = tiempo_total_sim/num_lotes
    
    df_metricas = pd.DataFrame([{
        'WIP': wip,
        'Cycle_time': cycle_time,
        'Throughput': throughput,
        'Takt_time': takt_time
    }])
    
    return df_resultados, df_utilizacion, df_metricas
