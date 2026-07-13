import os
import sys
from mysql.connector import Error

# Asegurar que el directorio raiz del proyecto este en el path de busqueda
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from Conexion.conexion import obtener_conexion

def validar_viabilidad_financiera():
    print("=" * 70)
    print("[*] EJECUTANDO SCRIPT DE VALIDACION DE VIABILIDAD FINANCIERA")
    print("=" * 70)
    
    conexion = obtener_conexion()
    if not conexion:
        print("[-] ERROR: No se pudo establecer conexion con la base de datos 'Mineria_BD'.")
        print("    Verifica que el servidor MySQL este activo y las credenciales en 'Conexion/.env'.")
        return

    cursor = None
    try:
        cursor = conexion.cursor()
        
        # 1. Consulta para extraer y cruzar las transacciones a traves de la alineacion de indices
        # (DetalleVenta, Detalle_Compraable e Historial_Comercial comparten correspondencia 1-a-1 por su fila origen)
        query = """
        SELECT 
            dv.Id_Detalle,
            dv.Codigo_de_Producto,
            dv.Cantidad_Adquirida AS Cantidad_Vendida,
            v.Precio_venta AS Venta_Total,
            c.Precio_Compra AS Compra_Total,
            dc.Cantidad AS Compra_Cantidad,
            p.Porcentaje_Descuento AS Descuento_Promocion
        FROM DetalleVenta dv
        JOIN Detalle_Compra dc ON dv.Id_Detalle = dc.Id_Detalle_Compra
        JOIN Historial_Comercial hc ON dv.Id_Detalle = hc.Id_Historial
        LEFT JOIN Venta v ON dv.Numero_Transaccion = v.Numero_Transaccion
        LEFT JOIN Compra c ON dc.Id_Compra = c.Id_Compra
        LEFT JOIN PROMOCION p ON hc.Id_promocion = p.Id_promocion;
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        total_transacciones = len(rows)
        if total_transacciones == 0:
            print("[-] ADVERTENCIA: La base de datos esta vacia. Ejecuta primero 'Carga/carga_bd.py'.")
            return
            
        print(f"[+] Conexion establecida. Analizando {total_transacciones} registros historicos...\n")
        
        transacciones_con_perdida = 0
        transacciones_salvadas = 0
        transacciones_insalvables = 0
        
        # Iterar sobre cada transaccion
        for row in rows:
            id_trans, cod_prod, cant_vendida, venta_total, compra_total, compra_qty, dcto_prom = row
            
            # Sanitizacion de datos
            cant_vendida = int(cant_vendida or 0)
            compra_qty = int(compra_qty or 1)
            venta_total = float(venta_total or 0.0)
            compra_total = float(compra_total or 0.0)
            dcto_prom = float(dcto_prom or 0.0)
            
            if cant_vendida <= 0 or compra_qty <= 0:
                continue
                
            # Calcular Costo y Precio de Venta Unitarios
            precio_venta_unitario_con_dcto = venta_total / cant_vendida
            costo_compra_unitario = compra_total / compra_qty
            
            # 2. Identificar perdidas (margen neto real con descuento actual <= 0)
            if precio_venta_unitario_con_dcto <= costo_compra_unitario:
                transacciones_con_perdida += 1
                
                # 3. Simular la "Restriccion Dinamica de Descuentos"
                # Primero estimamos el Precio de Venta Unitario Sin Descuento (base)
                factor_descuento = dcto_prom / 100.0
                if factor_descuento < 1.0:
                    precio_venta_unitario_sin_dcto = precio_venta_unitario_con_dcto / (1.0 - factor_descuento)
                else:
                    precio_venta_unitario_sin_dcto = precio_venta_unitario_con_dcto
                
                # Margen Base esperado = (Venta Sin Descuento - Costo de Compra) / Venta Sin Descuento
                if precio_venta_unitario_sin_dcto > 0:
                    margen_base = (precio_venta_unitario_sin_dcto - costo_compra_unitario) / precio_venta_unitario_sin_dcto
                else:
                    margen_base = 0.0
                    
                # Descuento Promocional Maximo = Margen Base - 5%
                descuento_maximo_permitido = margen_base - 0.05
                if descuento_maximo_permitido < 0.0:
                    descuento_maximo_permitido = 0.0
                    
                # Aplicamos la restriccion (el menor entre el descuento original y el limite corporativo)
                descuento_simulado = min(factor_descuento, descuento_maximo_permitido)
                
                # Precio de venta simulado con el nuevo descuento restringido
                precio_venta_simulado = precio_venta_unitario_sin_dcto * (1.0 - descuento_simulado)
                
                # 4. Validar si la transaccion salvo el margen del 5% respecto al costo de adquisicion
                margen_minimo_objetivo = costo_compra_unitario * 1.05
                if precio_venta_simulado >= margen_minimo_objetivo:
                    transacciones_salvadas += 1
                else:
                    transacciones_insalvables += 1

        # Calcular porcentajes
        pct_perdidas = (transacciones_con_perdida / total_transacciones) * 100
        
        # Evitar division por cero en las metricas de simulacion
        if transacciones_con_perdida > 0:
            pct_salvadas = (transacciones_salvadas / transacciones_con_perdida) * 100
            pct_insalvables = (transacciones_insalvables / transacciones_con_perdida) * 100
        else:
            pct_salvadas = 0.0
            pct_insalvables = 0.0

        # --- REPORTE DE SALIDA ---
        print("-" * 70)
        print("[+] RESULTADOS DEL ANALISIS FINANCIERO")
        print("-" * 70)
        print(f"Total de Transacciones Analizadas   : {total_transacciones}")
        print(f"Transacciones con Perdidas (Netas)   : {transacciones_con_perdida} ({pct_perdidas:.2f}%)")
        print(f"Transacciones Rentables (Originales) : {total_transacciones - transacciones_con_perdida} ({100 - pct_perdidas:.2f}%)")
        print("-" * 70)
        print("[+] SIMULACION: RESTRICCION DINAMICA DE DESCUENTOS (En perdidas)")
        print("-" * 70)
        print(f"-> Transacciones SALVADAS (Margen >= 5%): {transacciones_salvadas} ({pct_salvadas:.2f}%)")
        print(f"-> Transacciones INSALVABLES            : {transacciones_insalvables} ({pct_insalvables:.2f}%)")
        print("-" * 70)
        print("[!] CONCLUSIONES:")
        if transacciones_con_perdida == 0:
            print("  [OK] Excelente: No se detectan transacciones con perdidas en los datos cargados.")
        else:
            print(f"  [ALERTA] El {pct_perdidas:.2f}% de las ventas registraron perdidas financieras.")
            print(f"  [INFO] La Restriccion Dinamica de Descuentos logra rescatar a {transacciones_salvadas} transacciones")
            print(f"         ({pct_salvadas:.2f}% de las perdidas), asegurando un margen de ganancia >= 5% sobre el costo.")
            if transacciones_insalvables > 0:
                print(f"  [NOTA] Hay {transacciones_insalvables} transacciones que son INSALVABLES debido a que")
                print("         su Margen de Ganancia Base es menor al 5%, requiriendo ajuste de precios base.")
        print("=" * 70)

    except Error as e:
        print(f"[-] Ocurrio un error al consultar la base de datos: {e}")
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

if __name__ == "__main__":
    validar_viabilidad_financiera()
