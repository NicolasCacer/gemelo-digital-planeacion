import simpy, random, pandas as pd, numpy as np

def simular_produccion(df_desagregacion=None,
                       tamano_lote_max=100,
                       num_mezcla=2,
                       num_pasteurizacion=3,
                       num_llenado=2,
                       num_etiquetado=3,
                       num_camaras=1,
                       horas_dia=8,
                       dias_mes=30,
                       litros_por_unidad=0.5,
                       tiempo_mezcla=(15,25),
                       tiempo_pasteurizacion=(30,45),
                       tiempo_llenado=(10,15),
                       tiempo_etiquetado=(20,20),
                       tiempo_almacenamiento=(0,0),
                       n_iter=1,
                       turnos_por_dia=3,
                       df_plan_agg = None
                       ):

    resultados_totales = []
    utilizaciones_totales = []
    metricas_totales = []

    for iteracion in range(n_iter):
        random.seed(42 + iteracion)
        TIEMPO_TOTAL_DISPONIBLE = dias_mes * horas_dia * 60 * turnos_por_dia  # minutos considerando turnos

        resultados = []
        uso_mezcla, uso_pasteur, uso_llenado, uso_etiquetado, uso_camaras = [], [], [], [], []

                # --- Preparar lotes (ajustada para aprovechar el tamaño máximo) ---
        lotes_data = []
        if df_desagregacion is not None and not df_desagregacion.empty:
            bebidas = [c for c in df_desagregacion.columns if c != "mes"]
            for _, row in df_desagregacion.iterrows():
                mes = row["mes"]
                for bebida in bebidas:
                    litros = row[bebida]
                    if litros <= 0:
                        continue

                    unidades_totales = litros / litros_por_unidad
                    num_lotes = int(unidades_totales // tamano_lote_max)
                    resto = unidades_totales % tamano_lote_max

                    # Lotes completos
                    for i in range(num_lotes):
                        lotes_data.append({
                            "Lote": f"{bebida}_M{mes}_L{i+1}",
                            "Tamano": tamano_lote_max,
                            "Bebida": bebida,
                            "Mes": mes
                        })

                    # Último lote incompleto (si existe)
                    if resto > 0:
                        lotes_data.append({
                            "Lote": f"{bebida}_M{mes}_L{num_lotes+1}",
                            "Tamano": resto,
                            "Bebida": bebida,
                            "Mes": mes
                        })
        else:
            raise ValueError("df_desagregacion no puede ser None o vacío.")

        # --- Registrar uso ---
        def registrar_uso(env, recurso, lista_uso, evento, lote_id=None):
            lista_uso.append((env.now, recurso.count, len(recurso.queue), evento, recurso.capacity))
            if recurso.count > recurso.capacity:
                lote_info = f" Lote: {lote_id}" if lote_id else ""
                raise RuntimeError(f"ALERTA: Recurso {recurso} saturado a tiempo {env.now:.2f} min. "
                                   f"Capacidad={recurso.capacity}, Ocupados={recurso.count}.{lote_info}")

        # --- Proceso de cada lote ---
        def lote_proceso(env, lote, mezcla, pasteurizacion, llenado, etiquetado, camaras):
            inicio = env.now
            tamano = lote["Tamano"]

            for recurso, tiempo in [(mezcla, tiempo_mezcla), 
                                    (pasteurizacion, tiempo_pasteurizacion),
                                    (llenado, tuple(t * tamano / 100 for t in tiempo_llenado)),
                                    (etiquetado, tiempo_etiquetado)]:
                with recurso.request() as req:
                    yield req
                    registrar_uso(env, recurso, uso_recursos[recurso], "INICIO", lote_id=lote["Lote"])
                    yield env.timeout(random.uniform(*tiempo) if isinstance(tiempo, tuple) else tiempo)
                    registrar_uso(env, recurso, uso_recursos[recurso], "FIN", lote_id=lote["Lote"])

            # Cámara (0 minutos)
            with camaras.request() as req:
                yield req
                registrar_uso(env, camaras, uso_camaras, "INICIO", lote_id=lote["Lote"])
                registrar_uso(env, camaras, uso_camaras, "FIN", lote_id=lote["Lote"])

            tiempo_almacen = random.uniform(*tiempo_almacenamiento)
            yield env.timeout(tiempo_almacen)

            fin = env.now
            resultados.append({
                "Lote": lote["Lote"],
                "Bebida": lote["Bebida"],
                "Mes": lote["Mes"],
                "Tamano_botellas": tamano,
                "Creacion": inicio,
                "Entrega": fin,
                "Tiempo_sistema": fin - inicio,
                "Tiempo_almacenamiento": tiempo_almacen
            })

        # --- Llegada de lotes ---
        def generar_lotes(env):
            num_lotes_totales = len(lotes_data)
            tiempo_total_mes = dias_mes * horas_dia * 60 * turnos_por_dia
            tasa_llegada = tiempo_total_mes / num_lotes_totales
            for lote in lotes_data:
                yield env.timeout(random.uniform(tasa_llegada*0.8, tasa_llegada*1.2))
                env.process(lote_proceso(env, lote, mezcla, pasteurizacion, llenado, etiquetado, camaras))

        # --- Entorno SimPy ---
        env = simpy.Environment()
        mezcla = simpy.Resource(env, capacity=num_mezcla)
        pasteurizacion = simpy.Resource(env, capacity=num_pasteurizacion)
        llenado = simpy.Resource(env, capacity=num_llenado)
        etiquetado = simpy.Resource(env, capacity=num_etiquetado)
        camaras = simpy.Resource(env, capacity=num_camaras)

        uso_recursos = {
            mezcla: uso_mezcla,
            pasteurizacion: uso_pasteur,
            llenado: uso_llenado,
            etiquetado: uso_etiquetado
        }

        env.process(generar_lotes(env))
        try:
            env.run()
        except RuntimeError as e:
            print("SIMULACIÓN DETENIDA:", e)
            break

        # --- Resultados ---
        df_resultados = pd.DataFrame(resultados)

        # --- Calcular utilización ---
        def calcular_utilizacion(uso, tiempo_total_disponible):
            if not uso:
                return 0, 0, 0
            df = pd.DataFrame(uso, columns=["Tiempo","Ocupados","En_cola","Evento","Capacidad"]).sort_values("Tiempo")
            ocupados_area = sum((df.loc[i+1,"Tiempo"]-df.loc[i,"Tiempo"])*df.loc[i,"Ocupados"] for i in range(len(df)-1))
            cola_area = sum((df.loc[i+1,"Tiempo"]-df.loc[i,"Tiempo"])*df.loc[i,"En_cola"] for i in range(len(df)-1))
            capacidad = df["Capacidad"].iloc[0]
            util = ocupados_area / (capacidad * tiempo_total_disponible)
            cola_prom = cola_area / tiempo_total_disponible
            cola_max = df["En_cola"].max()
            return util, cola_prom, cola_max

        recursos = {
            "Mezcla": uso_mezcla,
            "Pasteurizacion": uso_pasteur,
            "Llenado": uso_llenado,
            "Etiquetado": uso_etiquetado,
            "Camaras": uso_camaras
        }

        lista_utilizacion = []
        for nombre, uso in recursos.items():
            util, cola_prom, cola_max = calcular_utilizacion(uso, TIEMPO_TOTAL_DISPONIBLE)
            lista_utilizacion.append({
                "Recurso": nombre,
                "Utilizacion": util,
                "Cola_promedio": cola_prom,
                "Cola_maxima": cola_max
            })
        df_utilizacion = pd.DataFrame(lista_utilizacion)

        # --- Métricas ---
        if not df_resultados.empty:
            wip = df_resultados["Tiempo_sistema"].sum()/TIEMPO_TOTAL_DISPONIBLE
            cycle_time = df_resultados["Tiempo_sistema"].mean()
            throughput = len(df_resultados)/TIEMPO_TOTAL_DISPONIBLE
            takt_time = TIEMPO_TOTAL_DISPONIBLE/len(df_resultados)
        else:
            wip = cycle_time = throughput = takt_time = 0

        df_metricas = pd.DataFrame([{
            "WIP": wip,
            "Cycle_time": cycle_time,
            "Throughput": throughput,
            "Takt_time": takt_time
        }])

        resultados_totales.append(df_resultados)
        utilizaciones_totales.append(df_utilizacion)
        metricas_totales.append(df_metricas)

    return pd.concat(resultados_totales, ignore_index=True), \
           pd.concat(utilizaciones_totales, ignore_index=True), \
           pd.concat(metricas_totales, ignore_index=True)
