import pandas as pd
import numpy as np
import datetime

# Funciones auxiliares para conversión de fechas (migradas desde Programa_bd)
def parsing_date(val):
    """
    Parsea de forma segura un string a un objeto datetime.date o retorna '00:00:00' para "No aplica" / nulos.
    """
    if pd.isna(val) or str(val).lower().strip() in ['no aplica', 'nan', '', '00:00:00', '0000-00-00']:
        return '00:00:00'
    try:
        # Intentar formato estándar del dataset: dd.mm.yyyy
        return pd.to_datetime(str(val), format='%d.%m.%Y').date()
    except Exception:
        try:
            return pd.to_datetime(str(val)).date()
        except Exception:
            return '00:00:00'

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
    Fase 3 (Estandarización y Conversión Estricta de Tipos / Casting):[cite: 1]
    1. Limpia y uniformiza formatos de texto, fechas y categorías.[cite: 1]
    2. Trata nombres de productos anómalos.
    3. Aplica casteo estricto de tipos de datos a nivel de columna (Casting - Fase 2 del orquestador anterior).[cite: 1]
    4. Trunca las longitudes de texto según los límites físicos de VARCHAR del DFR.[cite: 1]
    """
    df_clean = df.copy() #[cite: 1]

    # 1. Eliminar espacios sobrantes al inicio y final en columnas de texto[cite: 1]
    for col in df_clean.select_dtypes(include="object"): #[cite: 1]
        df_clean[col] = df_clean[col].str.strip() #[cite: 1]

    # --- NUEVO PROCESO: Nombres de producto puramente numéricos ---
    if "Product Name" in df_clean.columns:
        # Identifica si toda la cadena está compuesta solo por números
        es_solo_numeros = df_clean["Product Name"].astype(str).str.isnumeric()
        # Reemplaza los que cumplen la condición con el texto por defecto
        df_clean.loc[es_solo_numeros, "Product Name"] = "Producto Genérico"

    # 2. Estandarizar columnas categóricas a formato Title Case[cite: 1]
    columnas_categoricas = [ #[cite: 1]
        "Customer Segment", "Product Category", "Product Sub-Category", #[cite: 1]
        "Ship Mode", "State", "Region" #[cite: 1]
    ]
    for col in columnas_categoricas: #[cite: 1]
        if col in df_clean.columns: #[cite: 1]
            df_clean[col] = df_clean[col].str.title() #[cite: 1]

    # 3. Conversión de fechas y marcas de tiempo (Estandarización y Casteo Estricto)[cite: 1]
    columnas_date = [ #[cite: 1]
        "Ship Date", #[cite: 1]
        "Promotion Start Date", #[cite: 1]
        "Promotion End Date", #[cite: 1]
        "Lot Ingress Date", #[cite: 1]
        "Purchase Date" #[cite: 1]
    ]
    for col in columnas_date: #[cite: 1]
        if col in df_clean.columns: #[cite: 1]
            df_clean[col] = df_clean[col].apply(parsing_date) #[cite: 1]

    if "Order Date" in df_clean.columns: #[cite: 1]
        df_clean["Order Date"] = df_clean["Order Date"].apply(parsing_datetime) #[cite: 1]

    # 4. Casteo estricto de tipos numéricos (Casting)[cite: 1]
    if "Purchase ID" in df_clean.columns: #[cite: 1]
        df_clean["Purchase ID"] = df_clean["Purchase ID"].astype(str).str.replace("COMP-", "", regex=False) #[cite: 1]

    columnas_enteras = [ #[cite: 1]
        "Order ID", "Promotion Code", "Product Expiration Indicator",  #[cite: 1]
        "Warehouse Capacity", "Purchase Quantity", "Purchase Type ID", "Purchase ID" #[cite: 1]
    ]
    for col in columnas_enteras: #[cite: 1]
        if col in df_clean.columns: #[cite: 1]
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0).astype(int) #[cite: 1]

    columnas_decimales = [ #[cite: 1]
        "Discount", "Porcentaje_Descuento", "Profit", "Sales",  #[cite: 1]
        "Shipping Cost", "Unit Price", "Purchase Unit Cost", "Purchase Total Cost" #[cite: 1]
    ]
    for col in columnas_decimales: #[cite: 1]
        if col in df_clean.columns: #[cite: 1]
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0.0).astype(float).round(2) #[cite: 1]

    # 5. Truncamiento de cadenas de texto (Garantía de límites VARCHAR)[cite: 1]
    limites_varchar = { #[cite: 1]
        "Product Name": 150, #[cite: 1]
        "Warehouse Name": 150, #[cite: 1]
        "Warehouse Address": 255, #[cite: 1]
        "Warehouse District": 100, #[cite: 1]
        "Warehouse City": 100, #[cite: 1]
        "Product Category": 100, #[cite: 1]
        "Product Code": 50, #[cite: 1]
        "Warehouse Code": 50, #[cite: 1]
        "Lot Number": 50, #[cite: 1]
        "Ship Mode": 50, #[cite: 1]
        "Customer Segment": 50, #[cite: 1]
        "State": 50, #[cite: 1]
        "Region": 50, #[cite: 1]
        "Promotion Status": 50, #[cite: 1]
        "Product Container": 50, #[cite: 1]
        "Product Shelf Life": 50, #[cite: 1]
        "Warehouse Occupied Space": 50 #[cite: 1]
    }
    for col, limite in limites_varchar.items(): #[cite: 1]
        if col in df_clean.columns: #[cite: 1]
            # Rellenar nulos con vacío antes del casteo de texto para no truncar un float NaN[cite: 1]
            df_clean[col] = df_clean[col].astype(str).str.slice(0, limite) #[cite: 1]
    return df_clean #[cite: 1]
