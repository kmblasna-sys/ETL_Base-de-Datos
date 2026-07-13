import matplotlib.pyplot as plt
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "Conexion"))

from Conexion.conexion import obtener_conexion

def obtener_volumen_anomalias():
    conexion = obtener_conexion()
    if conexion is None:
        print("[!] No se pudo obtener conexión para el Gráfico 1.")
        return [], []

    cursor = conexion.cursor()

    query_regla1 = """
        SELECT COUNT(*) FROM (
            SELECT DISTINCT pp1.Codigo_Producto, pp1.Codigo_Promocion
            FROM Prod_Prom pp1
            JOIN Prod_Prom pp2 ON pp1.Codigo_Producto = pp2.Codigo_Producto
                               AND pp1.Codigo_Promocion <> pp2.Codigo_Promocion
            JOIN PROMOCION p1 ON pp1.Codigo_Promocion = p1.Id_promocion
            JOIN PROMOCION p2 ON pp2.Codigo_Promocion = p2.Id_promocion
            WHERE p1.Estado_Promocion = 'Activa'
              AND p2.Estado_Promocion = 'Activa'
              AND p1.Fecha_Inicio <= p2.Fecha_Finalizacion
              AND p2.Fecha_Inicio <= p1.Fecha_Finalizacion
        ) AS sub;
    """
    cursor.execute(query_regla1)
    total_traslapes = cursor.fetchone()[0]

    query_regla2 = """
        SELECT COUNT(DISTINCT v.Numero_Transaccion)
        FROM DetalleVenta dv
        JOIN Venta v ON dv.Numero_Transaccion = v.Numero_Transaccion
        JOIN Prod_Prom pp ON dv.Codigo_de_Producto = pp.Codigo_Producto
        JOIN PROMOCION p ON pp.Codigo_Promocion = p.Id_promocion
        WHERE v.Fecha_Hora_Emision < p.Fecha_Inicio
           OR v.Fecha_Hora_Emision > p.Fecha_Finalizacion;
    """
    cursor.execute(query_regla2)
    total_desfases = cursor.fetchone()[0]

    cursor.close()
    conexion.close()

    valores = [total_traslapes, total_desfases]
    etiquetas = ['Asignaciones con Traslape\n(Regla 1: Planificación)',
                 'Ventas Únicas Desfasadas\n(Regla 2: Operación Cajas)']
    return etiquetas, valores

def obtener_impacto_por_categoria():
    conexion = obtener_conexion()
    if conexion is None:
        print("[!] No se pudo obtener conexión para el Gráfico 2.")
        return [], []

    cursor = conexion.cursor()

    query_categoria = """
        SELECT
            c.nombre_categoria,
            ROUND(SUM(anomalias.Precio_venta), 2) AS Impacto
        FROM (
            -- Anomalía 1: Productos con múltiples promociones activas superpuestas en fechas
            SELECT DISTINCT v.Numero_Transaccion, dv.Codigo_de_Producto, v.Precio_venta
            FROM DetalleVenta dv
            JOIN Venta v ON dv.Numero_Transaccion = v.Numero_Transaccion
            JOIN Prod_Prom pp1 ON dv.Codigo_de_Producto = pp1.Codigo_Producto
            JOIN Prod_Prom pp2 ON pp1.Codigo_Producto = pp2.Codigo_Producto
                               AND pp1.Codigo_Promocion <> pp2.Codigo_Promocion
            JOIN PROMOCION p1 ON pp1.Codigo_Promocion = p1.Id_promocion
            JOIN PROMOCION p2 ON pp2.Codigo_Promocion = p2.Id_promocion
            WHERE p1.Estado_Promocion = 'Activa'
              AND p2.Estado_Promocion = 'Activa'
              AND p1.Fecha_Inicio <= p2.Fecha_Finalizacion
              AND p2.Fecha_Inicio <= p1.Fecha_Finalizacion
            
            UNION
            
            -- Anomalía 2: Ventas realizadas fuera del rango de vigencia de la promoción
            SELECT DISTINCT v.Numero_Transaccion, dv.Codigo_de_Producto, v.Precio_venta
            FROM DetalleVenta dv
            JOIN Venta v ON dv.Numero_Transaccion = v.Numero_Transaccion
            JOIN Prod_Prom pp ON dv.Codigo_de_Producto = pp.Codigo_Producto
            JOIN PROMOCION p ON pp.Codigo_Promocion = p.Id_promocion
            WHERE v.Fecha_Hora_Emision < p.Fecha_Inicio
               OR v.Fecha_Hora_Emision > p.Fecha_Finalizacion
        ) AS anomalias
        -- CORRECCIÓN: Unimos directamente con Producto y luego con Categoria
        JOIN Producto p ON anomalias.Codigo_de_Producto = p.Codigo_de_Producto
        JOIN Categoria c ON p.id_categoria = c.id_categoria
        GROUP BY c.nombre_categoria
        ORDER BY Impacto DESC;
    """
    cursor.execute(query_categoria)
    resultados = cursor.fetchall()

    cursor.close()
    conexion.close()

    categorias = [fila[0] for fila in resultados]
    impactos = [float(fila[1]) for fila in resultados]
    return categorias, impactos

plt.rcParams['font.sans-serif'] = 'Arial'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

labels_reglas, anomalias_reglas = obtener_volumen_anomalias()
categorias, impacto_usd = obtener_impacto_por_categoria()

if not anomalias_reglas or not impacto_usd:
    print("[!] No se pudieron obtener datos suficientes para graficar. Revisa la conexión.")
    sys.exit(1)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

colors_volumen = ['#0071CE', '#FFC220']
bars1 = ax1.bar(labels_reglas, anomalias_reglas, color=colors_volumen, width=0.4, edgecolor='none')
ax1.set_title('Gráfico 1: Volumen de Anomalías Detectadas por Regla Lógica', fontsize=12, pad=15, weight='bold')
ax1.set_ylabel('Cantidad de Registros Afectados', fontsize=10)
ax1.set_ylim(0, max(anomalias_reglas) * 1.15)
ax1.grid(axis='y', linestyle='--', alpha=0.5)
for bar in bars1:
    yval = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2, yval + (max(anomalias_reglas)*0.01),
              f'{yval:,}', ha='center', va='bottom', fontsize=10, weight='bold')

colors_cat = ['#0071CE', '#E53935', '#78909C']
bars2 = ax2.bar(categorias, impacto_usd, color=colors_cat[:len(categorias)], width=0.5, edgecolor='none')
ax2.set_title('Gráfico 2: Distribución del Impacto Total por Categoría Comercial', fontsize=12, pad=15, weight='bold')
ax2.set_ylabel('Impacto Económico Acumulado ($)', fontsize=10)
ax2.set_ylim(0, max(impacto_usd) * 1.2)
ax2.grid(axis='y', linestyle='--', alpha=0.5)
ax2.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, loc: "{:,}".format(int(x))))
for bar in bars2:
    yval = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width()/2, yval + (max(impacto_usd)*0.015),
              f'$ {yval:,.2f}', ha='center', va='bottom', fontsize=9, weight='bold')

plt.tight_layout()
ruta_salida = os.path.join(BASE_DIR , 'analisis_impacto_perdidas_promocionales_reales.png')
plt.savefig(ruta_salida, dpi=300)
print(f"[+] Gráfico guardado en: {ruta_salida}")
plt.show()