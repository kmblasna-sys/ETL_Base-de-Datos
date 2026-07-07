import pandas as pd
import numpy as np
import os

def registrar_log(mensaje):
    """
    Registra un mensaje de auditoría en la terminal y en un archivo de bitácora.
    """
    marca_tiempo = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{marca_tiempo}] {mensaje}"
    print(linea)
    with open("etl_fase1_auditoria.log", "a", encoding="utf-8") as f:
        f.write(linea + "\n")

def ejecutar_fase1_limpieza_walmart(ruta_archivo="/home/martin/Descargas/walmart Retail Data.csv"):
    """
    Fase 1 (Limpieza de Pseudo-Nulos y Resolución de Brechas / Enriquecimiento):
    1. Identifica y limpia pseudo-nulos en el archivo original.
    2. Resuelve brechas e inyecta campos por defecto de auditoría/derivados en el dataset plano.
    """
    if not os.path.exists(ruta_archivo):
        raise FileNotFoundError(f"No se encontró el archivo original en: {ruta_archivo}")

    # Cargar dataset
    df = pd.read_csv(ruta_archivo, index_col=False)
    
    patrones_nulos = ["Not Specified", "N/A", "None", "?"]
    
    # Reemplazar patrones de pseudo-nulos por nan real
    df.replace(patrones_nulos, np.nan, inplace=True)
    
    # Pre-identificar y pre-parsear todas las columnas de fecha a datetime para evitar problemas de orden en el bucle
    for col in df.columns:
        if "date" in col.lower():
            df[col] = df[col].replace(["No aplica", "no aplica", "nan", "None", "N/A", "?"], np.nan)
            df[col] = pd.to_datetime(df[col], format='%m-%d-%y', errors='coerce')
            
    # Rellenar nulos con media, moda o lógica temporal
    for columna in df.columns:
        if df[columna].isna().any():
            if "date" in columna.lower():
                # Rellenar columnas de fecha con lógica temporal
                if columna == 'Order Date':
                    moda_fecha = df[columna].mode()[0] if not df[columna].mode().empty else pd.Timestamp('2023-01-01')
                    df[columna] = df[columna].fillna(moda_fecha)
                elif columna == 'Ship Date' and 'Order Date' in df.columns:
                    df[columna] = df[columna].fillna(df['Order Date'] + pd.Timedelta(days=3))
                elif columna == 'Promotion Start Date' and 'Order Date' in df.columns:
                    df[columna] = df[columna].fillna(df['Order Date'])
                elif columna == 'Promotion End Date' and 'Promotion Start Date' in df.columns:
                    df[columna] = df[columna].fillna(df['Promotion Start Date'] + pd.Timedelta(days=30))
                elif columna in ['Lot Ingress Date', 'Purchase Date'] and 'Order Date' in df.columns:
                    df[columna] = df[columna].fillna(df['Order Date'] - pd.Timedelta(days=5))
                else:
                    moda_fecha = df[columna].mode()[0] if not df[columna].mode().empty else pd.Timestamp('2023-01-01')
                    df[columna] = df[columna].fillna(moda_fecha)
                registrar_log(f"Columna [{columna}]: Fecha -> Completada (Sin Nulos)")
                
            elif pd.api.types.is_numeric_dtype(df[columna]):
                media_calculada = df[columna].mean()
                df[columna] = df[columna].fillna(media_calculada)
                registrar_log(f"Columna [{columna}]: Numérica -> Media: {media_calculada:.2f}")
            else:
                modas = df[columna].mode()
                moda_elegida = modas[0] if not modas.empty else "No Modificable"
                df[columna] = df[columna].fillna(moda_elegida)
                registrar_log(f"Columna [{columna}]: Cualitativa -> Moda: '{moda_elegida}'")
        else:
            registrar_log(f"Columna [{columna}]: Correcta.")

    # Regresar todas las columnas de fecha a formato cadena dd.mm.yyyy al terminar el bucle
    for col in df.columns:
        if "date" in col.lower():
            df[col] = df[col].dt.strftime('%d.%m.%Y')

    # --- RESOLUCIÓN DE BRECHAS Y ENRIQUECIMIENTO (Fase 3 de Programa_bd original) ---
    registrar_log("[+] Iniciando enriquecimiento y resolución de brechas...")
    
    # 1. Porcentaje de descuento derivado a escala 100 (para DECIMAL(5,2))
    df['Porcentaje_Descuento'] = df['Discount'] * 100.0
    
    # 2. Inyección de valores por defecto para almacén
    df['Warehouse Type'] = 'Distribución General'
    df['Warehouse State'] = 'Activo'
    df['Warehouse Occupied Space'] = '0'
    
    # 3. Inyección de valores por defecto para compra
    df['Purchase Type ID'] = 1
    # 4. Cálculo de costo de compra total (Métrica derivada: Unit Cost * Quantity)
    df['Purchase Total Cost'] = df['Purchase Unit Cost'] * df['Purchase Quantity']
    
    registrar_log("[+] Enriquecimiento de datos completado.")
    return df
