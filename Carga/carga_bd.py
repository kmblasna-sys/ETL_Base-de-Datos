import sys
import os
import mysql.connector
from mysql.connector import Error
import pandas as pd
import numpy as np
from decimal import Decimal
import datetime
import unicodedata

# Agregar el directorio base al sys.path para importaciones estructuradas
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from Conexion.conexion import obtener_conexion
from Trasformacion.Main_transformacion import tablas_finales, todo_correcto

# Mapeo de claves internas (DataFrames de Programa_bd) a los nombres reales en Mineria_BD
MAPEO_TABLAS = {
    "tipo_promocion": "Tipo_Promocion",
    "producto": "Producto",
    "categoria": "Categoria",
    "venta": "Venta",
    "compra": "Compra",
    "ubicacion": "Ubicacion",
    "promocion": "PROMOCION",
    "producto_categoria": "Producto_categoria",
    "prod_prom": "Prod_Prom",
    "historial_comercial": "Historial_Comercial",
    "almacen": "Almacen",
    "lotes_de_inventario": "Lotes_de_Inventario",
    "detalleventa": "DetalleVenta",
    "detalle_compraable": "Detalle_Compraable"
}

# Orden de carga de las claves de tablas respetando las dependencias de claves foráneas (FK)
ORDEN_DE_CARGA_KEYS = [
    "tipo_promocion",
    "producto",
    "categoria",
    "venta",
    "compra",
    "ubicacion",
    "promocion",
    "producto_categoria",
    "prod_prom",
    "historial_comercial",
    "almacen",
    "lotes_de_inventario",
    "detalleventa",
    "detalle_compraable"
]

def normalizar_texto(text):
    """
    Normaliza el texto eliminando acentos y convirtiéndolo a minúsculas para comparaciones insensibles.
    """
    return "".join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    ).lower()

def cargar_datos_validados():
    """
    Verifica los resultados del control de calidad e inicia la carga atómica a MySQL.
    Utiliza las tablas ya creadas en la base de datos Mineria_BD, adaptando dinámicamente las columnas.
    """
    # 1. Gatekeeper: Validar si el control de calidad es satisfactorio
    if not todo_correcto:
        print("\n[-] PROCESO DENEGADO: El control de calidad (Main_transformacion.py) detectó inconsistencias de compatibilidad.")
        print("[-] Corrige las inconsistencias del dataset antes de proceder con la carga.")
        return False

    print("\n[+] CONTROL DE CALIDAD COMPLETADO CON ÉXITO. Preparando carga de datos...")

    # 2. Establecer conexión
    conexion = obtener_conexion()
    if not conexion:
        print("[-] Error de red: No se pudo conectar a la base de datos para iniciar la carga.")
        return False

    cursor = None
    try:
        # 3. Iniciar transacción relacional
        conexion.start_transaction()
        cursor = conexion.cursor()

        # Desactivar temporalmente FK checks para realizar el vaciado e inserción limpios
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        # Evitar que MySQL genere un ID secuencial al insertar 0 en columnas autoincrementales
        cursor.execute("SET @@session.sql_mode = 'NO_AUTO_VALUE_ON_ZERO';")

        print("[*] Vaciando tablas físicas antiguas para evitar duplicación...")
        for key in reversed(ORDEN_DE_CARGA_KEYS):
            nombre_tabla_real = MAPEO_TABLAS[key]
            cursor.execute(f"DELETE FROM {nombre_tabla_real};")

        # 4. Insertar registros
        for key in ORDEN_DE_CARGA_KEYS:
            df = tablas_finales[key].copy()
            nombre_tabla_real = MAPEO_TABLAS[key]
            
            # Obtener las columnas físicas reales de la tabla en MySQL
            cursor.execute(f"DESCRIBE {nombre_tabla_real};")
            db_columns = [row[0] for row in cursor.fetchall()]
            
            # Crear mapa de renombramiento de columnas para tolerar diferencias de mayúsculas/minúsculas y acentos
            mapeo_renombre = {}
            for df_col in df.columns:
                norm_df_col = normalizar_texto(df_col)
                for db_col in db_columns:
                    norm_db_col = normalizar_texto(db_col)
                    if norm_df_col == norm_db_col:
                        mapeo_renombre[df_col] = db_col
                        break
            
            # Renombrar columnas del DF
            df = df.rename(columns=mapeo_renombre)
            
            # Si en la base de datos hay columnas extras que no están en el DF (ej. 'Id_Historial' en PROMOCION), las agregamos como NULL
            for db_col in db_columns:
                if db_col not in df.columns:
                    df[db_col] = None
                    
            # Reordenar las columnas del DataFrame para que coincidan exactamente con la base de datos
            df = df[db_columns]
            
            def limpiar_valor(val):
                if pd.isna(val):
                    return None
                if isinstance(val, (np.integer, int)):
                    return int(val)
                if isinstance(val, (np.floating, float)):
                    return float(val)
                if isinstance(val, (datetime.date, datetime.datetime)):
                    return val.strftime('%Y-%m-%d %H:%M:%S') if isinstance(val, datetime.datetime) else val.strftime('%Y-%m-%d')
                return val

            columnas = ", ".join(db_columns)
            placeholders = ", ".join(["%s"] * len(db_columns))
            sql_insert = f"INSERT INTO {nombre_tabla_real} ({columnas}) VALUES ({placeholders})"
            
            # Convertir a lista de tuplas sanitizadas para la inserción masiva
            datos = [tuple(limpiar_valor(x) for x in row) for row in df.to_numpy()]
            
            print(f"[*] Insertando {len(datos)} registros en la tabla '{nombre_tabla_real}'...")
            cursor.executemany(sql_insert, datos)

        # Reactivar FK checks
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        
        # Guardar cambios
        conexion.commit()
        print("\n[+] ¡CARGA COMPLETADA CON ÉXITO! Todos los datos validados están en la base de datos Mineria_BD.")
        return True

    except Error as e:
        print(f"\n[-] ERROR CRÍTICO EN LA CARGA: {e}")
        if conexion:
            print("[-] Realizando ROLLBACK para mantener la base de datos limpia de cargas parciales...")
            conexion.rollback()
        return False

    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()
            print("[*] Conexión de base de datos cerrada de manera limpia.")

if __name__ == "__main__":
    cargar_datos_validados()
