import os
import sys
from mysql.connector import Error
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Asegurar que el directorio raiz del proyecto este en el path de busqueda
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from Conexion.conexion import obtener_conexion

def graficar_dispersion_margenes():
    print("=" * 70)
    print("[*] INICIANDO PROCESO DE GRAFICACION DE DISPERSION DE MARGENES")
    print("=" * 70)

    conexion = obtener_conexion()
    if not conexion:
        print("[-] ERROR: No se pudo establecer conexion con la base de datos 'Mineria_BD'.")
        return

    cursor = None
    try:
        cursor = conexion.cursor()
        
        # 1. Consulta SQL para extraer los datos de detalleventa, detalle_compraable, historial_comercial, venta, compra y promocion
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
            print("[-] ADVERTENCIA: La base de datos esta vacia. Carga los datos primero.")
            return

        print(f"[+] Datos recuperados. Procesando {total_transacciones} registros...")

        x_descuentos = []
        y_margenes = []

        for row in rows:
            id_trans, cod_prod, cant_vendida, venta_total, compra_total, compra_qty, dcto_prom = row
            
            # Sanitizacion de datos
            cant_vendida = int(cant_vendida or 0)
            compra_qty = int(compra_qty or 1)
            venta_total = float(venta_total or 0.0)
            compra_total = float(compra_total or 0.0)
            dcto_prom = float(dcto_prom or 0.0)

            if cant_vendida <= 0 or compra_qty <= 0 or venta_total <= 0:
                continue

            # Calcular Costo y Precio de Venta Unitarios
            precio_venta_unitario_con_dcto = venta_total / cant_vendida
            costo_compra_unitario = compra_total / compra_qty

            if precio_venta_unitario_con_dcto <= 0:
                continue

            # Margen Neto Real de Venta = ((Precio Venta Unitario Con Descuento - Costo Compra Unitario) / Precio Venta Unitario Con Descuento) * 100
            margen_neto_real = ((precio_venta_unitario_con_dcto - costo_compra_unitario) / precio_venta_unitario_con_dcto) * 100.0

            x_descuentos.append(dcto_prom)
            y_margenes.append(margen_neto_real)

        print(f"[+] Calculos finalizados para {len(x_descuentos)} transacciones validas.")

        # --- GENERACION DEL GRAFICO ---
        plt.figure(figsize=(10, 6))
        
        # Grafico de dispersion con transparencia
        plt.scatter(x_descuentos, y_margenes, color="steelblue", alpha=0.5, edgecolors="none", s=15, label="Transacciones")
        
        # Linea horizontal punteada de color rojo en Y = 0 (Punto de Equilibrio)
        plt.axhline(0, color="red", linestyle="--", linewidth=1.5, label="Punto de Equilibrio (y = 0%)")
        
        # Configuracion de titulos y etiquetas
        plt.title("Visualizacion y Dispersion de Margenes y Rentabilidad", fontsize=14, fontweight="bold", pad=15)
        plt.xlabel("Porcentaje de Descuento (%)", fontsize=11, labelpad=10)
        plt.ylabel("Margen Neto Real (%)", fontsize=11, labelpad=10)
        
        # Rejilla (Grid) de fondo para mejor legibilidad
        plt.grid(True, linestyle=":", alpha=0.6)
        
        # Ubicar leyenda
        plt.legend(loc="upper right")
        
        # Limitar visualmente los margenes extremos si existen errores de escala
        plt.ylim(min(y_margenes) - 10, 110)

        # Ruta de guardado
        output_path = os.path.join(BASE_DIR, "dispersion_margenes.png")
        # ==============================================================================
        
        # Guardar en alta resolucion
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close()

        print(f"[+] ¡Imagen generada con exito! Guardada en: {output_path}")
        print("=" * 70)

    except Error as e:
        print(f"[-] Ocurrio un error al interactuar con la base de datos: {e}")
    except Exception as ex:
        print(f"[-] Ocurrio un error inesperado al graficar: {ex}")
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

if __name__ == "__main__":
    graficar_dispersion_margenes()
