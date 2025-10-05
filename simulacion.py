import simpy, random, pandas as pd, numpy as np
def simular_produccion(df_desagregacion=None,
                                 num_lotes=None,
                                 tamano_lote_max=100,
                                 num_mezcla=2, num_pasteurizacion=2, num_llenado=2,
                                 num_etiquetado=2, num_camaras=1,
                                 horas_dia=8, dias_semana=6,
                                 velocidad_entrada=1.0):
    random.seed(42)

    # --- Parámetros del sistema ---
    MINUTOS_DIA_TRABAJO = horas_dia * 60
    DIAS_POR_SEMANA = dias_semana
    SEMANA_EN_MINUTOS = 7 * 24 * 60

    MEZCLA_TIEMPO = (15, 25)
    PASTEURIZACION_TIEMPO = (30, 45)
    LLENADO_TIEMPO_POR_100 = (10, 15)
    ETIQUETADO_TIEMPO = (20, 20)
    ALMACENAMIENTO_MAX = 48 * 60  # 2 días

    resultados = []
    uso_mezcla, uso_pasteur, uso_llenado, uso_etiquetado, uso_camara = [], [], [], [], []

    # --- Preparar lotes ---
    lotes_data = []
    if df_desagregacion is not None and not df_desagregacion.empty:
        for _, row in df_desagregacion.iterrows():
            bebida = row.get("bebida") or row.get("producto") or "Producto"
            mes = row.get("mes_continuo") or row.get("mes") or 1
            produccion = row.get("produccion_litros") or row.get("produccion") or 0
            if pd.isna(produccion) or produccion == 0:
                continue

            num_lotes_producto = max(1, int(produccion / tamano_lote_max))
            tamano_real = produccion / num_lotes_producto
            for i in range(num_lotes_producto):
                lotes_data.append({
                    "Lote": f"{bebida}_M{mes}_L{i+1}",
                    "Tamano": tamano_real,
                    "Bebida": bebida,
                    "Mes": mes
                })
    else:
        num_lotes = num_lotes or 10
        for i in range(1, num_lotes + 1):
            lotes_data.append({
                "Lote": f"L{i}",
                "Tamano": tamano_lote_max,
                "Bebida": "Genérica",
                "Mes": 1
            })

    # --- Funciones auxiliares ---
    def es_hora_laboral(tiempo):
        minutos_semana = tiempo % SEMANA_EN_MINUTOS
        dia_semana = minutos_semana // (24 * 60)
        hora_dia = minutos_semana % (24 * 60)
        return (dia_semana < DIAS_POR_SEMANA) and (hora_dia < MINUTOS_DIA_TRABAJO)

    def avanzar_a_hora_laboral(env):
        while not es_hora_laboral(env.now):
            yield env.timeout(1)

    def registrar_uso(env, recurso, lista_uso, evento):
        lista_uso.append((env.now, recurso.count, len(recurso.queue), evento))

    # --- Proceso de cada lote ---
    def lote_proceso(env, lote, mezcla, pasteurizacion, llenado, etiquetado, camara):
        inicio = env.now
        tamano = lote["Tamano"]

        yield from avanzar_a_hora_laboral(env)
        # Mezcla
        with mezcla.request() as req:
            yield req
            registrar_uso(env, mezcla, uso_mezcla, "INICIO")
            yield env.timeout(random.uniform(*MEZCLA_TIEMPO))
            registrar_uso(env, mezcla, uso_mezcla, "FIN")

        yield from avanzar_a_hora_laboral(env)
        # Pasteurización
        with pasteurizacion.request() as req:
            yield req
            registrar_uso(env, pasteurizacion, uso_pasteur, "INICIO")
            yield env.timeout(random.uniform(*PASTEURIZACION_TIEMPO))
            registrar_uso(env, pasteurizacion, uso_pasteur, "FIN")

        yield from avanzar_a_hora_laboral(env)
        # Llenado
        with llenado.request() as req:
            yield req
            registrar_uso(env, llenado, uso_llenado, "INICIO")
            factor = tamano / 100
            yield env.timeout(random.uniform(*LLENADO_TIEMPO_POR_100) * factor)
            registrar_uso(env, llenado, uso_llenado, "FIN")

        yield from avanzar_a_hora_laboral(env)
        # Etiquetado
        with etiquetado.request() as req:
            yield req
            registrar_uso(env, etiquetado, uso_etiquetado, "INICIO")
            yield env.timeout(random.uniform(*ETIQUETADO_TIEMPO))
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
            "Lote": lote["Lote"],
            "Bebida": lote["Bebida"],
            "Mes": lote["Mes"],
            "Tamano_botellas": tamano,
            "Inicio": inicio,
            "Fin": fin,
            "Tiempo_total": fin - inicio,
            "Tiempo_almacenamiento": tiempo_almacenamiento
        })

    # --- Llegada de lotes ---
    def generar_lotes(env):
        for lote in lotes_data:
            yield env.timeout(random.expovariate(1.0 / (30 * velocidad_entrada)))
            env.process(lote_proceso(env, lote, mezcla, pasteurizacion, llenado, etiquetado, camara))

    # --- Entorno SimPy ---
    env = simpy.Environment()
    mezcla = simpy.Resource(env, capacity=num_mezcla)
    pasteurizacion = simpy.Resource(env, capacity=num_pasteurizacion)
    llenado = simpy.Resource(env, capacity=num_llenado)
    etiquetado = simpy.Resource(env, capacity=num_etiquetado)
    camara = simpy.Resource(env, capacity=num_camaras)

    env.process(generar_lotes(env))
    env.run()

    # --- Resultados ---
    df_resultados = pd.DataFrame(resultados)
    tiempo_total_sim = df_resultados["Fin"].max() if not df_resultados.empty else 1

    # --- Utilización ---
    def calcular_utilizacion(uso, tiempo_total_sim):
        if not uso:
            return 0, 0, 0
        df = pd.DataFrame(uso, columns=["Tiempo", "Ocupados", "En_cola", "Evento"]).sort_values("Tiempo")
        ocupados_area = sum((df.loc[i + 1, "Tiempo"] - df.loc[i, "Tiempo"]) * df.loc[i, "Ocupados"] for i in range(len(df) - 1))
        cola_area = sum((df.loc[i + 1, "Tiempo"] - df.loc[i, "Tiempo"]) * df.loc[i, "En_cola"] for i in range(len(df) - 1))
        return ocupados_area / tiempo_total_sim, cola_area / tiempo_total_sim, df["En_cola"].max()

    recursos = {
        "Mezcla": uso_mezcla,
        "Pasteurizacion": uso_pasteur,
        "Llenado": uso_llenado,
        "Etiquetado": uso_etiquetado,
        "Camara": uso_camara,
    }

    lista_utilizacion = []
    for nombre, uso in recursos.items():
        util, cola, max_cola = calcular_utilizacion(uso, tiempo_total_sim)
        lista_utilizacion.append({
            "Recurso": nombre,
            "Utilizacion": util,
            "Cola_promedio": cola,
            "Cola_maxima": max_cola
        })
    df_utilizacion = pd.DataFrame(lista_utilizacion)

    # --- Métricas globales ---
    if not df_resultados.empty:
        wip = df_resultados["Tiempo_total"].sum() / tiempo_total_sim
        cycle_time = df_resultados["Tiempo_total"].mean()
        throughput = len(df_resultados) / tiempo_total_sim
        takt_time = tiempo_total_sim / len(df_resultados)
    else:
        wip = cycle_time = throughput = takt_time = 0

    df_metricas = pd.DataFrame([{
        "WIP": wip,
        "Cycle_time": cycle_time,
        "Throughput": throughput,
        "Takt_time": takt_time
    }])

    return df_resultados, df_utilizacion, df_metricas
