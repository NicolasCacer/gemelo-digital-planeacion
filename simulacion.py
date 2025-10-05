def simular_produccion(df_desagregacion=None,
                       num_lotes=None,
                       tamano_lote_max=100,
                       num_mezcla=2, num_pasteurizacion=2, num_llenado=2,
                       num_etiquetado=2, num_camaras=1):
    """
    Simula la producción de lotes usando SimPy.
    Puede usar datos de desagregación o valores manuales.

    Parámetros:
    - df_desagregacion: DataFrame con columnas ['bebida','mes_continuo','produccion_litros'] (de la desagregación)
    - num_lotes: Si no se pasa df_desagregacion, se usa este número de lotes aleatorios.
    - tamano_lote_max: Tamaño máximo por lote (solo si no se pasa df_desagregacion)
    - num_*: Recursos del sistema.
    """

    import simpy, random, pandas as pd
    import random
    random.seed(42)

    # ----- Datos del sistema -----
    MEZCLA_TIEMPO = (15, 25)
    PASTEURIZACION_TIEMPO = (30, 45)
    LLENADO_TIEMPO_POR_100 = (10, 15)
    ETIQUETADO_TIEMPO = (20, 20)
    ALMACENAMIENTO_MAX = 48 * 60  # minutos (2 días)

    resultados, uso_mezcla, uso_pasteur, uso_llenado, uso_etiquetado, uso_camara = (
        [], [], [], [], [], []
    )

    # ============================================================
    # 🔹 Si hay df_desagregacion, usarlo como base de los lotes
    # ============================================================
    lotes_data = []
    if df_desagregacion is not None and not df_desagregacion.empty:
        for _, row in df_desagregacion.iterrows():
            # --- Ajuste flexible de nombres de columnas ---
            bebida = (
                row.get("bebida")
                or row.get("producto")
                or row.get("Producto")
                or "Producto"
            )
            mes = (
                row.get("mes_continuo")
                or row.get("mes")
                or row.get("periodo")
                or 1
            )
            produccion = (
                row.get("produccion_litros")
                or row.get("produccion")
                or row.get("Producción")
                or 0
            )

            # --- Evitar valores nulos ---
            if pd.isna(bebida):
                bebida = "Producto"
            if pd.isna(mes):
                mes = 1
            if pd.isna(produccion):
                produccion = 0

            # --- Definir número de lotes en función del tamaño máximo ---
            num_lotes_producto = max(1, int(produccion / tamano_lote_max))
            for i in range(num_lotes_producto):
                lotes_data.append({
                    "Lote": f"{bebida}_M{mes}_L{i+1}",
                    "Tamano": min(tamano_lote_max, produccion / num_lotes_producto),
                    "Bebida": bebida,
                    "Mes": mes
                })
    else:
        # 🔹 Si no hay desagregación, usar modo aleatorio
        num_lotes = num_lotes or 10
        for i in range(1, num_lotes + 1):
            lotes_data.append({
                "Lote": f"L{i}",
                "Tamano": tamano_lote_max,
                "Bebida": "Genérica",
                "Mes": 1
            })


    # ============================================================
    # 🔹 Funciones internas
    # ============================================================
    def registrar_uso(env, recurso, lista_uso, evento):
        lista_uso.append((env.now, recurso.count, len(recurso.queue), evento))

    def lote_proceso(env, lote, mezcla, pasteurizacion, llenado, etiquetado, camara):
        inicio = env.now
        tamano = lote["Tamano"]

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
            factor = tamano / 100
            yield env.timeout(random.randint(*LLENADO_TIEMPO_POR_100) * factor)
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
            "Lote": lote["Lote"],
            "Bebida": lote["Bebida"],
            "Mes": lote["Mes"],
            "Tamano_botellas": tamano,
            "Inicio": inicio,
            "Fin": fin,
            "Tiempo_total": fin - inicio,
            "Tiempo_almacenamiento": tiempo_almacenamiento
        })

    # ============================================================
    # 🔹 Simulación SimPy
    # ============================================================
    def generar_lotes(env):
        for lote in lotes_data:
            yield env.timeout(random.randint(0, 30))
            env.process(lote_proceso(env, lote, mezcla, pasteurizacion, llenado, etiquetado, camara))

    import simpy
    env = simpy.Environment()
    mezcla = simpy.Resource(env, capacity=num_mezcla)
    pasteurizacion = simpy.Resource(env, capacity=num_pasteurizacion)
    llenado = simpy.Resource(env, capacity=num_llenado)
    etiquetado = simpy.Resource(env, capacity=num_etiquetado)
    camara = simpy.Resource(env, capacity=num_camaras)

    env.process(generar_lotes(env))
    env.run()

    df_resultados = pd.DataFrame(resultados)
    tiempo_total_sim = df_resultados["Fin"].max() if not df_resultados.empty else 1

    # ============================================================
    # 🔹 Métricas por recurso
    # ============================================================
    def calcular_utilizacion(uso, tiempo_total_sim):
        if not uso:
            return 0, 0, 0
        df = pd.DataFrame(uso, columns=["Tiempo", "Ocupados", "En_cola", "Evento"]).sort_values("Tiempo")
        ocupados_area = sum(
            (df.loc[i + 1, "Tiempo"] - df.loc[i, "Tiempo"]) * df.loc[i, "Ocupados"]
            for i in range(len(df) - 1)
        )
        cola_area = sum(
            (df.loc[i + 1, "Tiempo"] - df.loc[i, "Tiempo"]) * df.loc[i, "En_cola"]
            for i in range(len(df) - 1)
        )
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

    # ============================================================
    # 🔹 Métricas globales
    # ============================================================
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
