import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Agregar el directorio base al sys.path para importaciones
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "Conexion"))

from Conexion.conexion import obtener_conexion

def generar_reporte_dispersion(conexion=None):
    """
    Genera el gráfico de dispersión de márgenes clasificando cada transacción 
    por su riesgo de rentabilidad y lo guarda como 'dispersion_margenes.png'.
    """
    cerrar_conexion = False
    if conexion is None:
        conexion = obtener_conexion()
        cerrar_conexion = True

    if not conexion:
        raise ConnectionError("No se pudo conectar con la base de datos MySQL.")

    cursor = None
    try:
        cursor = conexion.cursor()
        query = """
        SELECT 
            dv.Id_Detalle,
            dv.Codigo_de_Producto,
            dv.Cantidad_Adquirida AS Cantidad_Vendida,
            dv.Precio_Unitario,
            dv.Utilidad,
            COALESCE(p.Porcentaje_Descuento, 0.0) AS Descuento_Promocion
        FROM DetalleVenta dv
        JOIN Historial_Comercial hc ON dv.Id_Detalle = hc.Id_Historial
        LEFT JOIN PROMOCION p ON hc.Id_promocion = p.Id_promocion;
        """
        cursor.execute(query)
        rows = cursor.fetchall()
    finally:
        if cursor: 
            cursor.close()
        if cerrar_conexion and conexion: 
            conexion.close()

    temp_data = []
    for row in rows:
        id_trans, cod_prod, cant_vendida, v_unit_sin_dcto, util, dcto_prom = row
        
        cant_vendida = int(cant_vendida or 0)
        if cant_vendida <= 0:
            continue
            
        v_unit_sin_dcto = float(v_unit_sin_dcto) if v_unit_sin_dcto is not None else 0.0
        util = float(util) if util is not None else 0.0
        dcto_prom = float(dcto_prom) if dcto_prom is not None else 0.0
        
        v_unit_con_dcto = v_unit_sin_dcto * (1.0 - dcto_prom / 100.0)
        c_unit = v_unit_con_dcto - (util / cant_vendida)
        util_sin_dcto = util + (v_unit_sin_dcto * cant_vendida * (dcto_prom / 100.0))

        if util >= 0:
            lbl_orig = 0
        else:
            if util_sin_dcto >= 0:
                lbl_orig = 1
            else:
                lbl_orig = 2
                
        # Calcular Margen Neto Real
        if v_unit_con_dcto > 0:
            margen_neto = ((v_unit_con_dcto - c_unit) / v_unit_con_dcto) * 100
        else:
            margen_neto = 0.0

        temp_data.append({
            'id': id_trans,
            'dcto': dcto_prom,
            'margen_neto': margen_neto,
            'lbl_orig': lbl_orig,
            'utilidad': util
        })

    df = pd.DataFrame(temp_data)
    if len(df) == 0:
        print("[-] No hay datos para graficar.")
        return None

    # Filtrar las anomalías
    class1 = df[df['lbl_orig'] == 1]
    class2 = df[df['lbl_orig'] == 2]

    df['Target_Riesgo'] = 0
    df.loc[df['id'].isin(class1['id']), 'Target_Riesgo'] = 1
    df.loc[df['id'].isin(class2['id']), 'Target_Riesgo'] = 2

    # Agrupar por clases para graficar
    x_descuentos = {0: [], 1: [], 2: []}
    y_margenes = {0: [], 1: [], 2: []}

    for _, r in df.iterrows():
        clase = int(r['Target_Riesgo'])
        x_descuentos[clase].append(r['dcto'])
        y_margenes[clase].append(r['margen_neto'])

    plt.figure(figsize=(10, 6.5))
    
    # Graficar
    if x_descuentos[0]:
        plt.scatter(x_descuentos[0], y_margenes[0], alpha=0.5, color="#2ecc71", edgecolors="none", label="Correcto / Rentable")
    if x_descuentos[1]:
        plt.scatter(x_descuentos[1], y_margenes[1], alpha=0.9, color="#e67e22", edgecolors="black", linewidths=0.5, s=40, label=f"Ajustar Dcto. ({len(class1)} Alertas)")
    if x_descuentos[2]:
        plt.scatter(x_descuentos[2], y_margenes[2], alpha=0.85, color="#e74c3c", edgecolors="black", linewidths=0.5, s=40, label=f"Ajustar Base ({len(class2)} Alertas Críticas)")
        
    plt.axhline(0, color="#34495e", linestyle="--", linewidth=1.8, label="Punto de Equilibrio (Margen = 0%)")
    
    plt.title("Visualización de Márgenes y Detección de Alertas de Pérdida", fontsize=13, fontweight="bold", pad=15)
    plt.xlabel("Porcentaje de Descuento Promocional Aplicado (%)", fontsize=10, labelpad=10)
    plt.ylabel("Margen Neto Real obtenido (%)", fontsize=10, labelpad=10)
    
    plt.text(5, 80, 
             "ZONA RENTABLE (Arriba de la línea punteada)\n"
             "ZONA DE PÉRDIDAS (Abajo de la línea punteada)", 
             fontsize=8.5, color="#555", style='italic',
             bbox=dict(facecolor='white', alpha=0.8, boxstyle='round,pad=0.5'))

    plt.grid(True, linestyle=":", alpha=0.5)
    plt.legend(loc="lower left", framealpha=0.9, fontsize=9.5)
    
    todas_y = list(df['margen_neto'])
    if todas_y:
        plt.ylim(min(todas_y) - 10, 110)

    output_path = os.path.join(BASE_DIR, "dispersion_margenes.png")
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    
    print(f"[+] Gráfico generado y guardado exitosamente en: {output_path}")
    return output_path

if __name__ == "__main__":
    try:
        generar_reporte_dispersion()
    except Exception as e:
        print(f"[-] Ocurrió un error al generar el gráfico: {e}")