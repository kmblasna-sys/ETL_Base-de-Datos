import os
import sys

# ==========================================
# 1. CONFIGURACIÓN DE RUTAS Y CONEXIÓN
# ==========================================
# Agregar el directorio base al sys.path para importaciones
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "Conexion"))

from Conexion.conexion import obtener_conexion

# ==========================================
# 2. INICIALIZACIÓN DE VARIABLES
# ==========================================
total_transacciones = 0
transacciones_con_perdida = 0
transacciones_salvadas = 0
transacciones_insalvables = 0
rows = []

print("===========================================================================")
print("[*] EJECUTANDO SCRIPT DE VALIDACION DE VIABILIDAD FINANCIERA")
print("===========================================================================")

# ==========================================
# 3. CONEXIÓN Y OBTENCIÓN DE DATOS
# ==========================================
conexion = None
cursor = None

try:
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    
    # Ejecutar el procedimiento almacenado
    
    cursor.execute("CALL sp_ObtenerDatosComerciales()") 
    
    rows = cursor.fetchall()
    total_transacciones = len(rows)
    
    print(f"\n[+] Conexion establecida. Analizando {total_transacciones} registros historicos...\n")

except Exception as e:
    print(f"\n[-] ERROR de Base de Datos: {e}")
    sys.exit(1)
finally:
    if cursor: cursor.close()
    if conexion: conexion.close()

# ==========================================
# 4. PROCESAMIENTO Y LÓGICA DE NEGOCIO
# ==========================================
for row in rows:
# Desempaquetado
    id_trans, cod_prod, cant_vendida, venta_total, compra_total, compra_qty, dcto_prom = row
    
    # Validaciones de seguridad
    if not cant_vendida or not compra_qty:
        continue
    
    # --- CONVERTIR TODO A FLOAT AQUÍ PARA EVITAR EL ERROR ---
    venta_total = float(venta_total) if venta_total is not None else 0.0
    compra_total = float(compra_total) if compra_total is not None else 0.0
    dcto_prom = float(dcto_prom) if dcto_prom is not None else 0.0
    # --------------------------------------------------------

    # Determinación de precios y costos unitarios netos
    precio_venta_unitario_con_dcto = venta_total / cant_vendida
    costo_compra_unitario = compra_total / compra_qty
    
    # 1. Filtración de Viabilidad (Ventas con margen neto real <= 0)
    if precio_venta_unitario_con_dcto <= costo_compra_unitario:
        transacciones_con_perdida += 1
        
        # Reconstrucción teórica del Precio Base Regular sin descuento
        factor_descuento = dcto_prom / 100.0
        precio_venta_unitario_sin_dcto = (
            precio_venta_unitario_con_dcto / (1.0 - factor_descuento) 
            if factor_descuento < 1.0 else precio_venta_unitario_con_dcto
        )
        
        # Cálculo del Margen Comercial Base de Catálogo
        margen_base = (
            (precio_venta_unitario_sin_dcto - costo_compra_unitario) / precio_venta_unitario_sin_dcto 
            if precio_venta_unitario_sin_dcto > 0 else 0.0
        )
            
        # 2. Simulación de Regla de Negocio: Descuento Máximo = Margen Base - 5%
        descuento_maximo_permitido = margen_base - 0.05
        if descuento_maximo_permitido < 0.0:
            descuento_maximo_permitido = 0.0
            
        # Aplicación restrictiva acotada al límite corporativo de seguridad
        descuento_simulado = min(factor_descuento, descuento_maximo_permitido)
        precio_venta_simulado = precio_venta_unitario_sin_dcto * (1.0 - descuento_simulado)
        
        # 3. Verificación del Margen de Ganancia Mínimo Obligatorio (>= 5% sobre el costo)
        margen_minimo_objetivo = costo_compra_unitario * 1.05
        if precio_venta_simulado >= margen_minimo_objetivo:
            transacciones_salvadas += 1
        else:
            transacciones_insalvables += 1

# ==========================================
# 5. CÁLCULO DE MÉTRICAS Y RENDERIZADO EN TERMINAL
# ==========================================
transacciones_rentables = total_transacciones - transacciones_con_perdida

# Cálculos de porcentajes seguros
pct_perdida = (transacciones_con_perdida / total_transacciones * 100) if total_transacciones > 0 else 0
pct_rentables = (transacciones_rentables / total_transacciones * 100) if total_transacciones > 0 else 0
pct_salvadas = (transacciones_salvadas / transacciones_con_perdida * 100) if transacciones_con_perdida > 0 else 0
pct_insalvables = (transacciones_insalvables / transacciones_con_perdida * 100) if transacciones_con_perdida > 0 else 0

print("---------------------------------------------------------------------------")
print("[+] RESULTADOS DEL ANALISIS FINANCIERO")
print("---------------------------------------------------------------------------")
print(f"\nTotal de Transacciones Analizadas   : {total_transacciones}")
print(f"Transacciones con Perdidas (Netas)  : {transacciones_con_perdida} ({pct_perdida:.2f}%)")
print(f"Transacciones Rentables (Originales): {transacciones_rentables} ({pct_rentables:.2f}%)\n")

print("---------------------------------------------------------------------------")
print("[+] SIMULACION: RESTRICCION DINAMICA DE DESCUENTOS (En perdidas)")
print("---------------------------------------------------------------------------")
print(f"\n-> Transacciones SALVADAS (Margen >= 5%) : {transacciones_salvadas} ({pct_salvadas:.2f}%)")
print(f"-> Transacciones INSALVABLES             : {transacciones_insalvables} ({pct_insalvables:.2f}%)\n")

print("---------------------------------------------------------------------------")
print("[!] CONCLUSIONES:")
print(f"[ALERTA] El {pct_perdida:.2f}% de las ventas registraron perdidas financieras.")
print(f"[INFO] La Restriccion Dinamica de Descuentos logra rescatar a {transacciones_salvadas} transacciones")
print(f"       ({pct_salvadas:.2f}% de las perdidas), asegurando un margen de ganancia >= 5% sobre el costo.")
print(f"[NOTA] Hay {transacciones_insalvables} transacciones que son INSALVABLES debido a que")
print(f"       su Margen de Ganancia Base es menor al 5%, requiriendo ajuste de precios base.")
print("===========================================================================")