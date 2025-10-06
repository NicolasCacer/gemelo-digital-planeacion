import simpy, random, pandas as pd, numpy as np

def simular_produccion(df_desagregacion=None,
                       tamano_lote_max=100,
                       num_mezcla=1,
                       num_pasteurizacion=1,
                       num_llenado=1,
                       num_etiquetado=1,
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
                       df_plan_agg=None
                       ):

    resultados_totales = []
    utilizaciones_totales = []
    metricas_totales = []

    if df_desagregacion is None or df_desagregacion.empty:
        raise ValueError("df_desagregacion no puede ser None o vacío.")

    bebidas = [c for c in df_desagregacion.columns if c != "mes"]

    for iteracion in range(n_iter):
        random.seed(42 + iteracion)

        resultados = []

        # --- Acumuladores de tiempo ocupado por recurso ---
        tiempo_ocupado = {
            "Mezcla": 0,
            "Pasteurizacion": 0,
            "Llenado": 0,
            "Etiquetado": 0,
            "Camaras": 0
        }

        # --- Preparar lotes por mes y bebida ---
        lotes_data = []
        for _, row in df_desagregacion.iterrows():
            mes = row["mes"]
            for bebida in bebidas:
                litros = row[bebida]
                if litros <= 0:
                    continue
                unidades_totales = litros / litros_por_unidad
                num_lotes = int(unidades_totales // tamano_lote_max)
                resto = unidades_totales % tamano_lote_max

                for i in range(num_lotes):
                    lotes_data.append({
                        "Lote": f"{bebida}_M{mes}_L{i+1}",
                        "Tamano": tamano_lote_max,
                        "Bebida": bebida,
                        "Periodo": mes
                    })
                if resto > 0:
                    lotes_data.append({
                        "Lote": f"{bebida}_M{mes}_L{num_lotes+1}",
                        "Tamano": resto,
                        "Bebida": bebida,
                        "Periodo": mes
                    })

        # --- Proceso de cada lote ---
        def lote_proceso(env, lote, mezcla, pasteurizacion, llenado, etiquetado, camaras):
            inicio = env.now
            tamano = lote["Tamano"]

            for nombre_recurso, recurso, tiempo in [
                ("Mezcla", mezcla, tiempo_mezcla),
                ("Pasteurizacion", pasteurizacion, tiempo_pasteurizacion),
                ("Llenado", llenado, tuple(t * tamano / 100 for t in tiempo_llenado)),
                ("Etiquetado", etiquetado, tiempo_etiquetado)
            ]:
                with recurso.request() as req:
                    yield req
                    t_inicio = env.now
                    yield env.timeout(random.uniform(*tiempo) if isinstance(tiempo, tuple) else tiempo)
                    t_fin = env.now
                    tiempo_ocupado[nombre_recurso] += t_fin - t_inicio

            # Cámara
            with camaras.request() as req:
                yield req
                t_inicio = env.now
                yield env.timeout(0)
                t_fin = env.now
                tiempo_ocupado["Camaras"] += t_fin - t_inicio

            tiempo_almacen = random.uniform(*tiempo_almacenamiento)
            yield env.timeout(tiempo_almacen)

            fin = env.now
            resultados.append({
                "Lote": lote["Lote"],
                "Bebida": lote["Bebida"],
                "Periodo": lote["Periodo"],
                "Tamano_botellas": tamano,
                "Creacion": inicio,
                "Entrega": fin,
                "Tiempo_sistema": fin - inicio,
                "Tiempo_almacenamiento": tiempo_almacen
            })

        # --- Generar lotes ---
        def generar_lotes(env, periodo):
            for lote in [l for l in lotes_data if l["Periodo"]==periodo]:
                yield env.timeout(0)
                env.process(lote_proceso(env, lote, mezcla, pasteurizacion, llenado, etiquetado, camaras))

        # --- Simulación mes a mes ---
        for mes in df_desagregacion["mes"].unique():
            if df_plan_agg is not None:
                row_plan = df_plan_agg[df_plan_agg["Periodo"]==mes].iloc[0]
                horas_totales = row_plan["Horas_Regulares"] + row_plan["Horas_Extras"]
                cap_mezcla = max(1, int(horas_totales / (horas_dia*turnos_por_dia)))
                cap_pasteur = cap_mezcla
                cap_llenado = cap_mezcla
                cap_etiquetado = cap_mezcla
            else:
                cap_mezcla = num_mezcla
                cap_pasteur = num_pasteurizacion
                cap_llenado = num_llenado
                cap_etiquetado = num_etiquetado

            env = simpy.Environment()
            mezcla = simpy.Resource(env, capacity=cap_mezcla)
            pasteurizacion = simpy.Resource(env, capacity=cap_pasteur)
            llenado = simpy.Resource(env, capacity=cap_llenado)
            etiquetado = simpy.Resource(env, capacity=cap_etiquetado)
            camaras = simpy.Resource(env, capacity=num_camaras)

            env.process(generar_lotes(env, mes))
            env.run()

            # Tiempo total disponible por mes
            TIEMPO_TOTAL_DISPONIBLE = dias_mes * horas_dia * 60 * turnos_por_dia

            # --- Calcular utilización ---
            lista_utilizacion = []
            for nombre, t_ocup in tiempo_ocupado.items():
                # dividir entre capacidad de máquinas
                if nombre == "Mezcla":
                    cap = num_mezcla
                elif nombre == "Pasteurizacion":
                    cap = num_pasteurizacion
                elif nombre == "Llenado":
                    cap = num_llenado
                elif nombre == "Etiquetado":
                    cap = num_etiquetado
                else:
                    cap = num_camaras
                util = t_ocup / (TIEMPO_TOTAL_DISPONIBLE * cap)
                lista_utilizacion.append({
                    "Periodo": mes,
                    "Recurso": nombre,
                    "Utilizacion": util,
                    "Cola_promedio": 0,
                    "Cola_maxima": 0
                })
            utilizaciones_totales.append(pd.DataFrame(lista_utilizacion))

            # --- Métricas por periodo ---
            df_mes = pd.DataFrame(resultados)
            df_mes_periodo = df_mes[df_mes["Periodo"]==mes]
            if not df_mes_periodo.empty:
                wip = df_mes_periodo["Tiempo_sistema"].sum()/TIEMPO_TOTAL_DISPONIBLE
                cycle_time = df_mes_periodo["Tiempo_sistema"].mean()
                throughput = len(df_mes_periodo)/TIEMPO_TOTAL_DISPONIBLE
                takt_time = TIEMPO_TOTAL_DISPONIBLE/len(df_mes_periodo)
            else:
                wip=cycle_time=throughput=takt_time=0
            metricas_totales.append(pd.DataFrame([{
                "Periodo": mes,
                "WIP": wip,
                "Cycle_time": cycle_time,
                "Throughput": throughput,
                "Takt_time": takt_time
            }]))

    return pd.DataFrame(resultados), \
           pd.concat(utilizaciones_totales, ignore_index=True), \
           pd.concat(metricas_totales, ignore_index=True)
