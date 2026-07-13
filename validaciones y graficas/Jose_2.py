import os
import sys
import matplotlib.pyplot as plt

# Asumiendo que cursor y BASE_DIR ya están definidos y listos...
# Agregar el directorio base al sys.path para importaciones
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "Conexion"))


from Conexion.conexion import obtener_conexion

conexion = None
cursor = None

try:
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    # 1. Llamar al procedimiento almacenado de MySQL
    cursor.execute("CALL sp_ObtenerDatosGraficoDispersion()")
    rows = cursor.fetchall()
    
    # 2. Inicializar listas para el gráfico de dispersión
    x_descuentos = []
    y_margenes = []
    
    # 3. Llenar las listas con los cálculos correspondientes
    for row in rows:
        id_trans, cod_prod, cant_vendida, venta_total, compra_total, compra_qty, dcto_prom = row
        
        # Omitir registros nulos o con cero cantidades para evitar divisiones por cero
        if not cant_vendida or not compra_qty:
            continue
            
        # Convertir TODO a float para evitar el error: TypeError: unsupported operand type(s)
        venta_total = float(venta_total) if venta_total is not None else 0.0
        compra_total = float(compra_total) if compra_total is not None else 0.0
        dcto_prom = float(dcto_prom) if dcto_prom is not None else 0.0
        
        # Calcular costos unitarios
        precio_venta_unitario = venta_total / cant_vendida
        costo_compra_unitario = compra_total / compra_qty
        
        # Solo calcular el margen si hay precio de venta
        if precio_venta_unitario > 0:
            # Fórmula clásica del Margen Neto Real: ((Venta - Costo) / Venta) * 100
            margen_neto = ((precio_venta_unitario - costo_compra_unitario) / precio_venta_unitario) * 100
            
            x_descuentos.append(dcto_prom)
            y_margenes.append(margen_neto)

    # 4. Verificación antes de graficar (para evitar errores si la consulta viene vacía)
    if y_margenes and x_descuentos:
        # Construcción y formateo estricto del scatter plot
        plt.figure(figsize=(10, 6))
        plt.scatter(x_descuentos, y_margenes, alpha=0.5, color="#6a0dad", edgecolors="none", label="Transacciones")
        plt.axhline(0, color="red", linestyle="--", linewidth=1.5, label="Punto de Equilibrio (y = 0%)")
        
        plt.title("Visualizacion y Dispersion de Margenes y Rentabilidad", fontsize=14, fontweight="bold", pad=15)
        plt.xlabel("Porcentaje de Descuento (%)", fontsize=11, labelpad=10)
        plt.ylabel("Margen Neto Real (%)", fontsize=11, labelpad=10)
        plt.grid(True, linestyle=":", alpha=0.6)
        plt.legend(loc="upper right")
        
        # Ajuste dinámico del eje Y basado en los datos
        plt.ylim(min(y_margenes) - 10, 110)

        # --- CAMBIO AQUÍ: Guardado directo en la carpeta principal (BASE_DIR) ---
        output_path = os.path.join(BASE_DIR, "dispersion_margenes.png")
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()
        # ------------------------------------------------------------------------
        
        print(f"[+] Gráfico generado y guardado exitosamente en: {output_path}")
    else:
        print("[-] No hay datos suficientes para generar el gráfico.")

except Exception as e:
    print(f"[-] Ocurrió un error al generar el gráfico: {e}")