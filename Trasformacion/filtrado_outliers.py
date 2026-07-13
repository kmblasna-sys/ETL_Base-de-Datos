import pandas as pd
import numpy as np
import os

def validar_outliers_iqr(input_source):
    """
    Fase 2: Identificación y exclusión de outliers estadísticos mediante el Rango Intercuartílico (IQR).
    Aplica el análisis sobre la columna 'Product Base Margin'.
    """
    if isinstance(input_source, str):
        if not os.path.exists(input_source):
            raise FileNotFoundError(f"No se encontró el archivo CSV en: {input_source}")
        datos_comerciales = pd.read_csv(input_source, index_col=False)
    else:
        datos_comerciales = input_source.copy()

    columna_analisis = "Product Base Margin"
    
    # Fase de cálculo estadístico intercuartílico
    q1 = datos_comerciales[columna_analisis].quantile(0.25)
    q3 = datos_comerciales[columna_analisis].quantile(0.75)
    iqr = q3 - q1
    
    # Establecimiento de los umbrales estadísticos de tolerancia
    limite_inferior = q1 - (1.5 * iqr)
    limite_superior = q3 + (1.5 * iqr)
    
    print(f"Límites de aceptación calculados: {limite_inferior} hasta {limite_superior}")
    
    datos_filtrados = []
    
    # Evaluación secuencial de la consistencia del margen por registro
    for idx, fila in datos_comerciales.iterrows():
        valor_actual = fila[columna_analisis]
        
        if pd.isna(valor_actual):
            print(f"Registro excluido por Outlier detectado en Row ID: {fila['Row ID']}")
            continue
            
        if (valor_actual >= limite_inferior) and (valor_actual <= limite_superior):
            datos_filtrados.append(fila)
        else:
            print(f"Registro excluido por Outlier detectado en Row ID: {fila['Row ID']}")
            
    return pd.DataFrame(datos_filtrados)
