import pandas as pd
import numpy as np
import datetime

# Funciones auxiliares para conversión de fechas (migradas desde Programa_bd)
def parsing_date(val):
    """
    Parsea de forma segura un string a un objeto datetime.date.
    """
    if pd.isna(val) or str(val).lower().strip() in ['no aplica', 'nan', '']:
        return None
    try:
        # Intentar formato estándar del dataset: dd.mm.yyyy
        return pd.to_datetime(str(val), format='%d.%m.%Y').date()
    except Exception:
        try:
            return pd.to_datetime(str(val)).date()
        except Exception:
            return None

def parsing_datetime(val):
    """
    Parsea de forma segura un string a un objeto datetime.datetime.
    """
    if pd.isna(val) or str(val).lower().strip() in ['no aplica', 'nan', '']:
        return None
    try:
        return pd.to_datetime(str(val), format='%d.%m.%Y').to_pydatetime()
    except Exception:
        try:
            return pd.to_datetime(str(val)).to_pydatetime()
        except Exception:
            return None

def estandarizar_datos(df):
    """
    Fase 3 (Estandarización y Conversión Estricta de Tipos / Casting):
    1. Limpia y uniformiza formatos de texto, fechas y categorías.
    2. Aplica casteo estricto de tipos de datos a nivel de columna (Casting - Fase 2 del orquestador anterior).
    3. Trunca las longitudes de texto según los límites físicos de VARCHAR del DFR.
    """
    df_clean = df.copy()

    # 1. Eliminar espacios sobrantes al inicio y final en columnas de texto
    for col in df_clean.select_dtypes(include="object"):
        df_clean[col] = df_clean[col].str.strip()

    # 2. Estandarizar columnas categóricas a formato Title Case
    columnas_categoricas = [
        "Customer Segment", "Product Category", "Product Sub-Category",
        "Ship Mode", "State", "Region"
    ]
    for col in columnas_categoricas:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].str.title()

    # 3. Conversión de fechas y marcas de tiempo (Estandarización y Casteo Estricto)
    columnas_date = [
        "Ship Date",
        "Promotion Start Date",
        "Promotion End Date",
        "Lot Ingress Date",
        "Purchase Date"
    ]
    for col in columnas_date:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(parsing_date)

    if "Order Date" in df_clean.columns:
        df_clean["Order Date"] = df_clean["Order Date"].apply(parsing_datetime)

    # 4. Casteo estricto de tipos numéricos (Casting)
    if "Purchase ID" in df_clean.columns:
        df_clean["Purchase ID"] = df_clean["Purchase ID"].astype(str).str.replace("COMP-", "", regex=False)

    columnas_enteras = [
        "Order ID", "Promotion Code", "Product Expiration Indicator", 
        "Warehouse Capacity", "Purchase Quantity", "Purchase Type ID", "Purchase ID"
    ]
    for col in columnas_enteras:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0).astype(int)

    columnas_decimales = [
        "Discount", "Porcentaje_Descuento", "Profit", "Sales", 
        "Shipping Cost", "Unit Price", "Purchase Unit Cost", "Purchase Total Cost"
    ]
    for col in columnas_decimales:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0.0).astype(float).round(2)

    # 5. Truncamiento de cadenas de texto (Garantía de límites VARCHAR)
    limites_varchar = {
        "Product Name": 150,
        "Warehouse Name": 150,
        "Warehouse Address": 255,
        "Warehouse District": 100,
        "Warehouse City": 100,
        "Product Category": 100,
        "Product Code": 50,
        "Warehouse Code": 50,
        "Lot Number": 50,
        "Ship Mode": 50,
        "Customer Segment": 50,
        "State": 50,
        "Region": 50,
        "Promotion Status": 50,
        "Product Container": 50,
        "Product Shelf Life": 50
    }
    for col, limite in limites_varchar.items():
        if col in df_clean.columns:
            # Rellenar nulos con vacío antes del casteo de texto para no truncar un float NaN
            df_clean[col] = df_clean[col].astype(str).str.slice(0, limite)
    return df_clean
