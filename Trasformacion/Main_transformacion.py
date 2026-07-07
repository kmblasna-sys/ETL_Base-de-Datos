import os
import sys
import pandas as pd

# Definición de rutas
CSV_PATH = "ruta de dataset"
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# Asegurar el acceso al directorio local de Transformación
sys.path.append(OUTPUT_DIR)

# Importación de módulos locales de transformación previa (limpieza, outliers y estandarización)
from limpieza_nulos import ejecutar_fase1_limpieza_walmart
from filtrado_outliers import validar_outliers_iqr
from estandarizacion import estandarizar_datos
from validacion_compatibilidad import ejecutar_mapeo_y_validacion

def ejecutar_pipeline_completo():
    """
    Ejecuta el pipeline completo de ETL:
    1. Limpieza de pseudo-nulos y resolución de brechas.
    2. Tratamiento de outliers.
    3. Estandarización de formatos y casteo.
    4. Mapeo estructural relacional y validación de compatibilidad.
    """
    print("Iniciando el orquestador del pipeline de base de datos...")
    print(f"Ruta del dataset: {CSV_PATH}\n")

    # ==============================================================================
    # PROCESAMIENTO PREVIO (LIMPIEZA, ENRIQUECIMIENTO, OUTLIERS Y ESTANDARIZACIÓN)
    # ==============================================================================
    print("=== INICIANDO TRANSFORMACIÓN PREVIA A LA CARGA ===")

    # 1. Limpieza de pseudo-nulos e Inyección de Gaps / Enriquecimiento (limpieza_nulos.py)
    print("\n[Fase 1 & Enriquecimiento] Limpieza de pseudo-nulos y resolución de brechas...")
    df_fase1 = ejecutar_fase1_limpieza_walmart(CSV_PATH)
    fase1_csv = os.path.join(os.path.dirname(OUTPUT_DIR), "walmart_Retail_Data_Fase1_Limpio.csv")
    df_fase1.to_csv(fase1_csv, index=False)
    print(f"[+] Archivo CSV generado para Fase 1: {fase1_csv}")

    # 2. Filtrado Estadístico de Outliers (filtrado_outliers.py)
    print("\n[Fase 2] Tratamiento de outliers (IQR) en Product Base Margin...")
    df_fase2 = validar_outliers_iqr(df_fase1)
    fase2_csv = os.path.join(os.path.dirname(OUTPUT_DIR), "walmart_Retail_Data_Fase2_Outliers.csv")
    df_fase2.to_csv(fase2_csv, index=False)
    print(f"[+] Archivo CSV generado para Fase 2: {fase2_csv}")

    # 3. Estandarización de Formatos y Conversión Estricta de Tipos (estandarizacion.py)
    print("\n[Fase 3 & Casting] Estandarización de datos y casteo de tipos...")
    df_fase3 = estandarizar_datos(df_fase2)
    fase3_csv = os.path.join(os.path.dirname(OUTPUT_DIR), "walmart_Retail_Data_Fase3_Estandarizado.csv")
    df_fase3.to_csv(fase3_csv, index=False)
    print(f"[+] Archivo CSV generado para Fase 3: {fase3_csv}")

    # ==============================================================================
    # MAPEO ESTRUCTURAL Y VALIDACIÓN DE COMPATIBILIDAD (MÓDULO SEPARADO)
    # ==============================================================================
    tablas, correcto = ejecutar_mapeo_y_validacion(df_fase3)
    
    return tablas, correcto

# Ejecución del pipeline para exportar los objetos para carga_bd.py
tablas_finales, todo_correcto = ejecutar_pipeline_completo()

if __name__ == "__main__":
    print("\n[+] Orquestación de pipeline finalizada.")
