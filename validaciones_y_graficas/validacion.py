import sys
import os
import datetime
import warnings

warnings.filterwarnings("ignore", category=UserWarning)
# Agregar el directorio base al sys.path para importaciones
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "Conexion"))

try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = None
    np = None

try:
    from Conexion.conexion import obtener_conexion
except ImportError:
    obtener_conexion = None


def obtener_lotes_perecederos():
    """Retorna lista de lotes perecederos y sus días restantes sin requerir pandas."""
    if not obtener_conexion:
        return []

    conn = obtener_conexion()
    if not conn:
        return []

    query = """
        SELECT 
            l.Numero_Lote,
            l.Fecha_ingreso,
            p.Indicador_de_Caducidad,
            p.Vida_Util,
            a.Capacidad_Total,
            a.Espacio_ocupado,
            v.Fecha_Hora_Emision AS Fecha_Transaccion
        FROM Lotes_de_Inventario l
        INNER JOIN Detalle_Compra dc ON l.Numero_Lote = dc.Numero_Lote
        INNER JOIN Producto p ON dc.Codigo_de_Producto = p.Codigo_de_Producto
        INNER JOIN Almacen a ON l.Codigo_de_Almacen = a.Codigo_Almacen
        INNER JOIN DetalleVenta dv ON p.Codigo_de_Producto = dv.Codigo_de_Producto
        INNER JOIN Venta v ON dv.Numero_Transaccion = v.Numero_Transaccion
        WHERE p.Indicador_de_Caducidad = 1;
    """
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query)
    filas = cursor.fetchall()
    cursor.close()
    conn.close()

    datos = []
    for fila in filas:
        fecha_ingreso = fila.get('Fecha_ingreso')
        fecha_transaccion = fila.get('Fecha_Transaccion')

        if isinstance(fecha_ingreso, str):
            try:
                fecha_ingreso = datetime.datetime.fromisoformat(fecha_ingreso)
            except Exception:
                fecha_ingreso = None
        elif isinstance(fecha_ingreso, datetime.date) and not isinstance(fecha_ingreso, datetime.datetime):
            fecha_ingreso = datetime.datetime.combine(fecha_ingreso, datetime.time.min)

        if isinstance(fecha_transaccion, str):
            try:
                fecha_transaccion = datetime.datetime.fromisoformat(fecha_transaccion)
            except Exception:
                fecha_transaccion = None
        elif isinstance(fecha_transaccion, datetime.date) and not isinstance(fecha_transaccion, datetime.datetime):
            fecha_transaccion = datetime.datetime.combine(fecha_transaccion, datetime.time.min)

        vida_util = fila.get('Vida_Util')
        try:
            anos = float(str(vida_util).strip().split()[0])
        except Exception:
            anos = 2.0
        dias_vida = anos * 365

        fecha_venc = None
        dias_restantes = None
        if fecha_ingreso and fecha_transaccion:
            fecha_venc = fecha_ingreso + datetime.timedelta(days=dias_vida)
            dias_restantes = (fecha_venc - fecha_transaccion).days

        if dias_restantes is None:
            prioridad = 'Normal'
        elif dias_restantes < 60:
            prioridad = 'Crítico'
        elif dias_restantes <= 180:
            prioridad = 'Alerta'
        else:
            prioridad = 'Normal'

        datos.append({
            'Numero_Lote': fila.get('Numero_Lote'),
            'Fecha_ingreso': fecha_ingreso,
            'Fecha_Transaccion': fecha_transaccion,
            'Vida_Util': fila.get('Vida_Util'),
            'Capacidad_Total': fila.get('Capacidad_Total'),
            'Espacio_ocupado': fila.get('Espacio_ocupado'),
            'Dias_Restantes': dias_restantes if dias_restantes is not None else -1,
            'Prioridad_Rotacion': 2 if dias_restantes is not None and dias_restantes < 60 else 1 if dias_restantes is not None and dias_restantes <= 180 else 0,
            'Prioridad_Label': prioridad,
        })
    return datos


def obtener_df_perecederos():
    """Retorna el DataFrame con lotes perecederos y sus días restantes."""
    if not obtener_conexion:
        return pd.DataFrame()

    conn = obtener_conexion()
    if not conn:
        return pd.DataFrame()

    query = """
        SELECT 
            l.Numero_Lote,
            l.Fecha_ingreso,
            p.Indicador_de_Caducidad,
            p.Vida_Util,
            a.Capacidad_Total,
            a.Espacio_ocupado,
            v.Fecha_Hora_Emision AS Fecha_Transaccion
        FROM Lotes_de_Inventario l
        INNER JOIN Detalle_Compra dc ON l.Numero_Lote = dc.Numero_Lote
        INNER JOIN Producto p ON dc.Codigo_de_Producto = p.Codigo_de_Producto
        INNER JOIN Almacen a ON l.Codigo_de_Almacen = a.Codigo_Almacen
        INNER JOIN DetalleVenta dv ON p.Codigo_de_Producto = dv.Codigo_de_Producto
        INNER JOIN Venta v ON dv.Numero_Transaccion = v.Numero_Transaccion
        WHERE p.Indicador_de_Caducidad = 1;
    """

    df_perecederos = pd.read_sql(query, conn)
    conn.close()

    if df_perecederos.empty:
        return df_perecederos

    df_perecederos['Fecha_Ingreso_dt'] = pd.to_datetime(df_perecederos['Fecha_ingreso'], errors='coerce')
    df_perecederos['Fecha_Transaccion_dt'] = pd.to_datetime(df_perecederos['Fecha_Transaccion'], errors='coerce')
    df_perecederos['Anos_Vida_Util'] = df_perecederos['Vida_Util'].astype(str).str.extract(r'(\d+)').astype(float).fillna(2)
    df_perecederos['Dias_Vida_Util'] = df_perecederos['Anos_Vida_Util'] * 365
    df_perecederos['Fecha_Vencimiento'] = df_perecederos['Fecha_Ingreso_dt'] + pd.to_timedelta(df_perecederos['Dias_Vida_Util'], unit='D')
    df_perecederos['Dias_Restantes'] = (df_perecederos['Fecha_Vencimiento'] - df_perecederos['Fecha_Transaccion_dt']).dt.days

    def etiquetar_prioridad(dias):
        if pd.isna(dias):
            return 0
        if dias < 60:
            return 2
        elif dias <= 180:
            return 1
        return 0

    df_perecederos['Prioridad_Rotacion'] = df_perecederos['Dias_Restantes'].apply(etiquetar_prioridad)
    df_perecederos['Prioridad_Label'] = df_perecederos['Prioridad_Rotacion'].map({2: 'Crítico', 1: 'Alerta', 0: 'Normal'})
    df_perecederos['Dias_Restantes'] = df_perecederos['Dias_Restantes'].fillna(-1).astype(int)
    return df_perecederos


def validar_modelo_caducidad():
    if not obtener_conexion:
        print("=========================================================================")
        print("[!] ERROR: No se pudo establecer comunicacion con el servidor MySQL.")
        print("=========================================================================")
        return

    conn = obtener_conexion()
    
    query = """
        SELECT 
            l.Numero_Lote,
            l.Fecha_ingreso,
            p.Indicador_de_Caducidad,
            p.Vida_Util,
            a.Capacidad_Total,
            a.Espacio_ocupado,
            v.Fecha_Hora_Emision AS Fecha_Transaccion
        FROM Lotes_de_Inventario l
        INNER JOIN Detalle_Compra dc ON l.Numero_Lote = dc.Numero_Lote
        INNER JOIN Producto p ON dc.Codigo_de_Producto = p.Codigo_de_Producto
        INNER JOIN Almacen a ON l.Codigo_de_Almacen = a.Codigo_Almacen
        INNER JOIN DetalleVenta dv ON p.Codigo_de_Producto = dv.Codigo_de_Producto
        INNER JOIN Venta v ON dv.Numero_Transaccion = v.Numero_Transaccion
        WHERE p.Indicador_de_Caducidad = 1;
    """
    
    df_perecederos = pd.read_sql(query, conn)
    conn.close()

    print("=========================================================================")
    print("[*] EJECUTANDO SCRIPT DE VALIDACION DE RIESGO DE CADUCIDAD")
    print("=========================================================================")
    print("[+] Conexion establecida. Analizando registros historicos...")
    print("-------------------------------------------------------------------------")

    if df_perecederos.empty:
        print("[!] AVISO: No se encontraron registros dinamicos para evaluar.")
        print("=========================================================================")
        return

    df_perecederos['Fecha_Ingreso_dt'] = pd.to_datetime(df_perecederos['Fecha_ingreso'], errors='coerce')
    df_perecederos['Fecha_Transaccion_dt'] = pd.to_datetime(df_perecederos['Fecha_Transaccion'], errors='coerce')
    
    df_perecederos['Anos_Vida_Util'] = df_perecederos['Vida_Util'].str.extract(r'(\d+)').astype(float).fillna(2)
    df_perecederos['Dias_Vida_Util'] = df_perecederos['Anos_Vida_Util'] * 365
    df_perecederos['Fecha_Vencimiento'] = df_perecederos['Fecha_Ingreso_dt'] + pd.to_timedelta(df_perecederos['Dias_Vida_Util'], unit='D')
    
    df_perecederos['Dias_Restantes'] = (df_perecederos['Fecha_Vencimiento'] - df_perecederos['Fecha_Transaccion_dt']).dt.days

    def etiquetar_prioridad(dias):
        if pd.isna(dias): return 0
        if dias < 60: return 2
        elif dias <= 180: return 1
        else: return 0

    df_perecederos['Prioridad_Rotacion'] = df_perecederos['Dias_Restantes'].apply(etiquetar_prioridad)
    df_perecederos['Espacio_ocupado_num'] = pd.to_numeric(df_perecederos['Espacio_ocupado'], errors='coerce').fillna(0)

    X = df_perecederos[['Capacidad_Total', 'Espacio_ocupado_num', 'Dias_Restantes']].fillna(0)
    y = df_perecederos['Prioridad_Rotacion']

    try:
        from sklearn.model_selection import train_test_split
        from sklearn.tree import DecisionTreeClassifier
        from sklearn.metrics import confusion_matrix
    except ImportError as e:
        print("=========================================================================")
        print("[!] ERROR: No se pudo cargar sklearn para validar el modelo.")
        print(f"[!] {e}")
        print("=========================================================================")
        return

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42)

    clf_tree = DecisionTreeClassifier(max_depth=4, random_state=42)
    clf_tree.fit(X_train, y_train)
    y_pred = clf_tree.predict(X_test)

    total_lotes = len(df_perecederos)
    criticos_reales = np.sum(y == 2)
    alertas_reales = np.sum(y == 1)
    estables_reales = np.sum(y == 0)

    cm = confusion_matrix(y_test, y_pred, labels=[0, 1, 2])
    lotes_criticos_test = cm[2][2]
    omisiones_criticas = cm[2][0] + cm[2][1]

    print("[+] RESULTADOS DEL ANALISIS DE INVENTARIO EN RIESGO")
    print("-------------------------------------------------------------------------")
    print(f"Total de Transacciones Analizadas     : {total_lotes}")
    print(f"Lotes en Estado Estable  (Clase 0)    : {estables_reales} ({ (estables_reales/total_lotes)*100:.2f}%)")
    print(f"Lotes en Estado de Alerta (Clase 1)   : {alertas_reales} ({ (alertas_reales/total_lotes)*100:.2f}%)")
    print(f"Lotes en Estado Critico   (Clase 2)   : {criticos_reales} ({ (criticos_reales/total_lotes)*100:.2f}%)")
    print("-------------------------------------------------------------------------")
    print("[+] EVALUACION TECNICA DEL CLASIFICADOR (Restriccion Dinamica)")
    print("-------------------------------------------------------------------------")
    print(f"-> Lotes Criticos Detectados Exitosamente : {lotes_criticos_test}")
    print(f"-> Lotes Criticos Omitidos (Falsos Neg.)  : {omisiones_criticas}")
    print("-------------------------------------------------------------------------")
    print("[!] CONCLUSIONES:")
    
    if omisiones_criticas == 0:
        print(f"   [ALERTA] El {(criticos_reales/total_lotes)*100:.2f}% de las transacciones registraron productos proximos a caducar.")
        print(f"   [INFO] El Clasificador de Caducidad logra un RECALL del 100% en la muestra de validacion.")
        print(f"          Se interceptaron los lotes de riesgo con 0 omisiones operativas.")
        print(f"   [NOTE] El sistema puede inyectar estas alertas limpias de manera segura en el Frontend")
        print(f"          para activar el disparador de salida prioritaria y mitigar mermas financieras.")
    else:
        print(f"   [ALERTA] El {(criticos_reales/total_lotes)*100:.2f}% de las mercancias presenta criticidad temporal.")
        print(f"   [INFO] Se detecto una tasa marginal de omision de {omisiones_criticas} lote(s) fuera del radar academico.")
        print(f"   [NOTE] Se sugiere un ajuste fino en el hiperparametro de profundidad para optimizar las alertas.")
        
    print("=========================================================================")

if __name__ == "__main__":
    validar_modelo_caducidad()


def generar_histograma_vencimientos():
    if not obtener_conexion:
        print("=========================================================================")
        print("[!] ERROR: No se pudo establecer comunicacion con el servidor MySQL.")
        print("=========================================================================")
        return

    conn = obtener_conexion()
    
    query = """
        SELECT 
            l.Fecha_ingreso,
            p.Vida_Util,
            v.Fecha_Hora_Emision AS Fecha_Transaccion
        FROM Lotes_de_Inventario l
        INNER JOIN Detalle_Compra dc ON l.Numero_Lote = dc.Numero_Lote
        INNER JOIN Producto p ON dc.Codigo_de_Producto = p.Codigo_de_Producto
        INNER JOIN DetalleVenta dv ON p.Codigo_de_Producto = dv.Codigo_de_Producto
        INNER JOIN Venta v ON dv.Numero_Transaccion = v.Numero_Transaccion
        WHERE p.Indicador_de_Caducidad = 1;
    """
    
    df_caducidad = pd.read_sql(query, conn)
    conn.close()

    if df_caducidad.empty:
        print("[!] AVISO: No hay datos perecederos para graficar.")
        return

    df_caducidad['Fecha_Ingreso_dt'] = pd.to_datetime(df_caducidad['Fecha_ingreso'], errors='coerce')
    df_caducidad['Fecha_Transaccion_dt'] = pd.to_datetime(df_caducidad['Fecha_Transaccion'], errors='coerce')
    
    df_caducidad['Anos_Vida_Util'] = df_caducidad['Vida_Util'].str.extract(r'(\d+)').astype(float).fillna(2)
    df_caducidad['Dias_Vida_Util'] = df_caducidad['Anos_Vida_Util'] * 365
    df_caducidad['Fecha_Vencimiento'] = df_caducidad['Fecha_Ingreso_dt'] + pd.to_timedelta(df_caducidad['Dias_Vida_Util'], unit='D')
    
    df_caducidad['Dias_Restantes'] = (df_caducidad['Fecha_Vencimiento'] - df_caducidad['Fecha_Transaccion_dt']).dt.days

    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError as e:
        print("=========================================================================")
        print("[!] ERROR: No se pudo cargar matplotlib/seaborn para generar el gráfico.")
        print(f"[!] {e}")
        print("=========================================================================")
        return

    plt.figure(figsize=(10, 5.5))
    
    sns.histplot(df_caducidad['Dias_Restantes'], bins=35, color='#2c3e50', kde=True, edgecolor='white', alpha=0.85)
    
    plt.axvline(x=60, color='#e74c3c', linestyle='--', linewidth=2, label='Umbral Critico (< 60 dias)')
    plt.axvline(x=180, color='#f39c12', linestyle='--', linewidth=2, label='Umbral Alerta (60 - 180 dias)')
    
    plt.title('HISTOGRAMA: DISTRIBUCION DE VIDA UTIL RESTANTE EN STOCK', fontsize=12, fontweight='bold', pad=15)
    plt.xlabel('Dias Remanentes antes del Vencimiento Fisico', fontsize=10)
    plt.ylabel('Frecuencia Absoluta (Cantidad de Transacciones de Lotes)', fontsize=10)
    plt.legend(loc='upper right')
    plt.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('histograma_vencimientos.png', dpi=300)
    plt.close()
    
    print("=========================================================================")
    print("[+] HISTOGRAMA GENERADO CON EXITO")
    print("=========================================================================")
    print(f"[#] Registros procesados de la base de datos : {len(df_caducidad)}")
    print("[#] Archivo guardado correctamente como       : histograma_vencimientos.png")
    print("=========================================================================")

if __name__ == "__main__":
    generar_histograma_vencimientos()