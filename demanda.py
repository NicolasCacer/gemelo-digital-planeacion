import pandas as pd

def generar_pronostico_demanda(meses, valor_predeterminado=100):
    demanda = pd.DataFrame({
        "Mes": meses,
        "Demanda": [valor_predeterminado]*len(meses)
    })
    return demanda