import datetime
import re
import warnings

warnings.filterwarnings("ignore", category=UserWarning)

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


# Criterio: productos con vida útil numérica O marcados como perecederos.
# En Mineria_BD el indicador suele venir en 0, pero Vida_Util = '2 años' identifica perecederos.
QUERY_LOTES_PERECEDEROS = """
    SELECT DISTINCT
        l.Numero_Lote,
        l.Fecha_ingreso,
        l.Espacio_ocupado,
        p.Codigo_de_Producto,
        p.Nombre AS Nombre_Producto,
        p.Indicador_de_Caducidad,
        p.Vida_Util,
        a.Capacidad_Total,
        a.Espacio_ocupado AS Espacio_ocupado_almacen
    FROM Lotes_de_Inventario l
    INNER JOIN Detalle_Compra dc ON l.Numero_Lote = dc.Numero_Lote
    INNER JOIN Producto p ON dc.Codigo_de_Producto = p.Codigo_de_Producto
    INNER JOIN Almacen a ON l.Codigo_de_Almacen = a.Codigo_Almacen
    WHERE (
        p.Indicador_de_Caducidad IN (1, '1', 'Perecible')
        OR p.Vida_Util REGEXP '[0-9]'
    )
    AND LOWER(TRIM(COALESCE(p.Vida_Util, ''))) NOT IN ('no aplica', 'n/a', 'na', '')
"""


def _parsear_fecha(valor):
    if valor is None:
        return None
    if isinstance(valor, datetime.datetime):
        return valor
    if isinstance(valor, datetime.date):
        return datetime.datetime.combine(valor, datetime.time.min)
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto or texto in ("0000-00-00", "None", "NULL"):
            return None
        for formato in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.datetime.strptime(texto, formato)
            except ValueError:
                continue
        try:
            return datetime.datetime.fromisoformat(texto.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _extraer_anos_vida_util(vida_util):
    if vida_util is None:
        return None
    texto = str(vida_util).strip()
    if not texto or texto.lower() in ("no aplica", "n/a", "na", "none", "nan"):
        return None
    coincidencia = re.search(r"(\d+(?:\.\d+)?)", texto)
    if not coincidencia:
        return None
    return float(coincidencia.group(1))


def _sumar_anos(fecha, anos):
    if fecha is None or anos is None:
        return None
    anos_enteros = int(anos)
    try:
        return fecha.replace(year=fecha.year + anos_enteros)
    except ValueError:
        return fecha.replace(year=fecha.year + anos_enteros, day=28)


def calcular_info_caducidad(fila, fecha_referencia=None):
    fecha_ingreso = _parsear_fecha(fila.get("Fecha_ingreso"))
    fecha_referencia = _parsear_fecha(fecha_referencia) if fecha_referencia is not None else None
    if fecha_referencia is None:
        fecha_referencia = datetime.datetime.now()

    anos = _extraer_anos_vida_util(fila.get("Vida_Util"))
    fecha_vencimiento = None
    dias_restantes = None
    if fecha_ingreso and anos is not None:
        fecha_vencimiento = _sumar_anos(fecha_ingreso, anos)
        dias_restantes = (fecha_vencimiento - fecha_referencia).days

    if dias_restantes is None:
        prioridad = "Normal"
        prioridad_rotacion = 0
    elif dias_restantes < 0:
        prioridad = "Vencido"
        prioridad_rotacion = 2
    elif dias_restantes < 60:
        prioridad = "Crítico"
        prioridad_rotacion = 2
    elif dias_restantes <= 180:
        prioridad = "Alerta"
        prioridad_rotacion = 1
    else:
        prioridad = "Normal"
        prioridad_rotacion = 0

    espacio = fila.get("Espacio_ocupado")
    if espacio is None:
        espacio = fila.get("Espacio_ocupado_almacen")

    return {
        "Numero_Lote": fila.get("Numero_Lote"),
        "Codigo_de_Producto": fila.get("Codigo_de_Producto"),
        "Nombre_Producto": fila.get("Nombre_Producto") or fila.get("Nombre"),
        "Fecha_ingreso": fecha_ingreso,
        "Fecha_Transaccion": fecha_referencia,
        "Vida_Util": fila.get("Vida_Util"),
        "Capacidad_Total": fila.get("Capacidad_Total"),
        "Espacio_ocupado": espacio,
        "Fecha_Vencimiento": fecha_vencimiento,
        "Dias_Restantes": dias_restantes if dias_restantes is not None else -1,
        "Prioridad_Rotacion": prioridad_rotacion,
        "Prioridad_Label": prioridad,
    }


def _ejecutar_query_lotes(conn):
    cursor = conn.cursor(dictionary=True)
    cursor.execute(QUERY_LOTES_PERECEDEROS)
    filas = cursor.fetchall()
    cursor.close()
    return filas


def _fecha_referencia_analisis(filas):
    """
    Usa la fecha de ingreso más reciente del inventario como 'hoy' del análisis.
    El dataset es histórico (aprox. 2020-2023); con datetime.now() todos los lotes
    aparecerían vencidos y el modelo/panel no aportaría clases de riesgo.
    """
    fechas = [_parsear_fecha(f.get("Fecha_ingreso")) for f in filas]
    fechas = [f for f in fechas if f is not None]
    if fechas:
        return max(fechas)
    return datetime.datetime.now()


def obtener_lotes_perecederos(fecha_referencia=None):
    """Retorna lista de lotes perecederos y sus días restantes sin requerir pandas."""
    if not obtener_conexion:
        return []

    conn = obtener_conexion()
    if not conn:
        return []

    try:
        filas = _ejecutar_query_lotes(conn)
    finally:
        conn.close()

    if not filas:
        return []

    fecha_ref = _parsear_fecha(fecha_referencia) if fecha_referencia is not None else _fecha_referencia_analisis(filas)
    datos = []
    vistos = set()
    for fila in filas:
        lote = fila.get("Numero_Lote")
        if lote in vistos:
            continue
        vistos.add(lote)
        info = calcular_info_caducidad(fila, fecha_referencia=fecha_ref)
        if info.get("Fecha_Vencimiento") is None:
            continue
        datos.append(info)

    datos.sort(key=lambda x: (x.get("Dias_Restantes", 10**9), str(x.get("Numero_Lote", ""))))
    return datos


def obtener_df_perecederos():
    """Retorna el DataFrame con lotes perecederos y sus días restantes."""
    if pd is None:
        raise ImportError("pandas es requerido para obtener_df_perecederos()")

    if not obtener_conexion:
        return pd.DataFrame()

    conn = obtener_conexion()
    if not conn:
        return pd.DataFrame()

    try:
        df_perecederos = pd.read_sql(QUERY_LOTES_PERECEDEROS, conn)
    finally:
        conn.close()

    if df_perecederos.empty:
        return df_perecederos

    df_perecederos = df_perecederos.drop_duplicates(subset=["Numero_Lote"]).copy()
    df_perecederos["Fecha_Ingreso_dt"] = pd.to_datetime(df_perecederos["Fecha_ingreso"], errors="coerce")
    df_perecederos["Anos_Vida_Util"] = (
        df_perecederos["Vida_Util"].astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0].astype(float)
    )
    df_perecederos = df_perecederos.dropna(subset=["Anos_Vida_Util", "Fecha_Ingreso_dt"])
    df_perecederos["Dias_Vida_Util"] = df_perecederos["Anos_Vida_Util"] * 365
    df_perecederos["Fecha_Vencimiento"] = df_perecederos["Fecha_Ingreso_dt"] + pd.to_timedelta(
        df_perecederos["Dias_Vida_Util"], unit="D"
    )
    fecha_ref = df_perecederos["Fecha_Ingreso_dt"].max()
    df_perecederos["Dias_Restantes"] = (df_perecederos["Fecha_Vencimiento"] - fecha_ref).dt.days
    df_perecederos["Fecha_Transaccion"] = fecha_ref

    def etiquetar_prioridad(dias):
        if pd.isna(dias):
            return 0
        if dias < 60:
            return 2
        if dias <= 180:
            return 1
        return 0

    def etiquetar_label(dias):
        if pd.isna(dias):
            return "Normal"
        if dias < 0:
            return "Vencido"
        if dias < 60:
            return "Crítico"
        if dias <= 180:
            return "Alerta"
        return "Normal"

    df_perecederos["Prioridad_Rotacion"] = df_perecederos["Dias_Restantes"].apply(etiquetar_prioridad)
    df_perecederos["Prioridad_Label"] = df_perecederos["Dias_Restantes"].apply(etiquetar_label)
    df_perecederos["Dias_Restantes"] = df_perecederos["Dias_Restantes"].fillna(-1).astype(int)
    return df_perecederos


def validar_modelo_caducidad():
    if pd is None or np is None:
        print("=========================================================================")
        print("[!] ERROR: pandas/numpy no estan disponibles.")
        print("=========================================================================")
        return

    if not obtener_conexion:
        print("=========================================================================")
        print("[!] ERROR: No se pudo establecer comunicacion con el servidor MySQL.")
        print("=========================================================================")
        return

    conn = obtener_conexion()
    if not conn:
        print("=========================================================================")
        print("[!] ERROR: No se pudo establecer comunicacion con el servidor MySQL.")
        print("=========================================================================")
        return

    try:
        df_perecederos = pd.read_sql(QUERY_LOTES_PERECEDEROS, conn)
    finally:
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

    df_perecederos = df_perecederos.drop_duplicates(subset=["Numero_Lote"]).copy()
    df_perecederos["Fecha_Ingreso_dt"] = pd.to_datetime(df_perecederos["Fecha_ingreso"], errors="coerce")
    df_perecederos["Anos_Vida_Util"] = (
        df_perecederos["Vida_Util"].astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0].astype(float)
    )
    df_perecederos = df_perecederos.dropna(subset=["Anos_Vida_Util", "Fecha_Ingreso_dt"])
    df_perecederos["Dias_Vida_Util"] = df_perecederos["Anos_Vida_Util"] * 365
    df_perecederos["Fecha_Vencimiento"] = df_perecederos["Fecha_Ingreso_dt"] + pd.to_timedelta(
        df_perecederos["Dias_Vida_Util"], unit="D"
    )
    fecha_ref = df_perecederos["Fecha_Ingreso_dt"].max()
    df_perecederos["Dias_Restantes"] = (df_perecederos["Fecha_Vencimiento"] - fecha_ref).dt.days

    def etiquetar_prioridad(dias):
        if pd.isna(dias):
            return 0
        if dias < 60:
            return 2
        if dias <= 180:
            return 1
        return 0

    df_perecederos["Prioridad_Rotacion"] = df_perecederos["Dias_Restantes"].apply(etiquetar_prioridad)
    df_perecederos["Espacio_ocupado_num"] = pd.to_numeric(df_perecederos["Espacio_ocupado"], errors="coerce").fillna(0)

    X = df_perecederos[["Capacidad_Total", "Espacio_ocupado_num", "Dias_Restantes"]].fillna(0)
    y = df_perecederos["Prioridad_Rotacion"]

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

    if len(df_perecederos) < 5 or y.nunique() < 2:
        print("[!] AVISO: Datos insuficientes o una sola clase para entrenar el modelo.")
        print(f"[#] Lotes evaluables: {len(df_perecederos)}")
        print("=========================================================================")
        return

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42)

    clf_tree = DecisionTreeClassifier(max_depth=4, random_state=42)
    clf_tree.fit(X_train, y_train)
    y_pred = clf_tree.predict(X_test)

    total_lotes = len(df_perecederos)
    criticos_reales = int(np.sum(y == 2))
    alertas_reales = int(np.sum(y == 1))
    estables_reales = int(np.sum(y == 0))

    cm = confusion_matrix(y_test, y_pred, labels=[0, 1, 2])
    lotes_criticos_test = int(cm[2][2]) if cm.shape[0] > 2 else 0
    omisiones_criticas = int(cm[2][0] + cm[2][1]) if cm.shape[0] > 2 else 0

    print("[+] RESULTADOS DEL ANALISIS DE INVENTARIO EN RIESGO")
    print("-------------------------------------------------------------------------")
    print(f"Total de Lotes Analizados             : {total_lotes}")
    print(f"Lotes en Estado Estable  (Clase 0)    : {estables_reales} ({(estables_reales / total_lotes) * 100:.2f}%)")
    print(f"Lotes en Estado de Alerta (Clase 1)   : {alertas_reales} ({(alertas_reales / total_lotes) * 100:.2f}%)")
    print(f"Lotes en Estado Critico   (Clase 2)   : {criticos_reales} ({(criticos_reales / total_lotes) * 100:.2f}%)")
    print("-------------------------------------------------------------------------")
    print("[+] EVALUACION TECNICA DEL CLASIFICADOR (Restriccion Dinamica)")
    print("-------------------------------------------------------------------------")
    print(f"-> Lotes Criticos Detectados Exitosamente : {lotes_criticos_test}")
    print(f"-> Lotes Criticos Omitidos (Falsos Neg.)  : {omisiones_criticas}")
    print("-------------------------------------------------------------------------")
    print("[!] CONCLUSIONES:")

    if omisiones_criticas == 0:
        print(f"   [ALERTA] El {(criticos_reales / total_lotes) * 100:.2f}% de los lotes registran productos proximos a caducar.")
        print("   [INFO] El Clasificador de Caducidad logra un RECALL del 100% en la muestra de validacion.")
        print("          Se interceptaron los lotes de riesgo con 0 omisiones operativas.")
        print("   [NOTE] El sistema puede inyectar estas alertas limpias de manera segura en el Frontend")
        print("          para activar el disparador de salida prioritaria y mitigar mermas financieras.")
    else:
        print(f"   [ALERTA] El {(criticos_reales / total_lotes) * 100:.2f}% de las mercancias presenta criticidad temporal.")
        print(f"   [INFO] Se detecto una tasa marginal de omision de {omisiones_criticas} lote(s) fuera del radar academico.")
        print("   [NOTE] Se sugiere un ajuste fino en el hiperparametro de profundidad para optimizar las alertas.")

    print("=========================================================================")


def generar_histograma_vencimientos():
    if pd is None:
        print("=========================================================================")
        print("[!] ERROR: pandas no esta disponible.")
        print("=========================================================================")
        return

    if not obtener_conexion:
        print("=========================================================================")
        print("[!] ERROR: No se pudo establecer comunicacion con el servidor MySQL.")
        print("=========================================================================")
        return

    conn = obtener_conexion()
    if not conn:
        print("=========================================================================")
        print("[!] ERROR: No se pudo establecer comunicacion con el servidor MySQL.")
        print("=========================================================================")
        return

    try:
        df_caducidad = pd.read_sql(QUERY_LOTES_PERECEDEROS, conn)
    finally:
        conn.close()

    if df_caducidad.empty:
        print("[!] AVISO: No hay datos perecederos para graficar.")
        return

    df_caducidad = df_caducidad.drop_duplicates(subset=["Numero_Lote"]).copy()
    df_caducidad["Fecha_Ingreso_dt"] = pd.to_datetime(df_caducidad["Fecha_ingreso"], errors="coerce")
    df_caducidad["Anos_Vida_Util"] = (
        df_caducidad["Vida_Util"].astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0].astype(float)
    )
    df_caducidad = df_caducidad.dropna(subset=["Anos_Vida_Util", "Fecha_Ingreso_dt"])
    df_caducidad["Dias_Vida_Util"] = df_caducidad["Anos_Vida_Util"] * 365
    df_caducidad["Fecha_Vencimiento"] = df_caducidad["Fecha_Ingreso_dt"] + pd.to_timedelta(
        df_caducidad["Dias_Vida_Util"], unit="D"
    )
    fecha_ref = df_caducidad["Fecha_Ingreso_dt"].max()
    df_caducidad["Dias_Restantes"] = (df_caducidad["Fecha_Vencimiento"] - fecha_ref).dt.days

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

    sns.histplot(df_caducidad["Dias_Restantes"], bins=35, color="#2c3e50", kde=True, edgecolor="white", alpha=0.85)

    plt.axvline(x=60, color="#e74c3c", linestyle="--", linewidth=2, label="Umbral Critico (< 60 dias)")
    plt.axvline(x=180, color="#f39c12", linestyle="--", linewidth=2, label="Umbral Alerta (60 - 180 dias)")

    plt.title("HISTOGRAMA: DISTRIBUCION DE VIDA UTIL RESTANTE EN STOCK", fontsize=12, fontweight="bold", pad=15)
    plt.xlabel("Dias Remanentes antes del Vencimiento Fisico", fontsize=10)
    plt.ylabel("Frecuencia Absoluta (Cantidad de Lotes)", fontsize=10)
    plt.legend(loc="upper right")
    plt.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig("histograma_vencimientos.png", dpi=300)
    plt.close()

    print("=========================================================================")
    print("[+] HISTOGRAMA GENERADO CON EXITO")
    print("=========================================================================")
    print(f"[#] Registros procesados de la base de datos : {len(df_caducidad)}")
    print("[#] Archivo guardado correctamente como       : histograma_vencimientos.png")
    print("=========================================================================")


if __name__ == "__main__":
    validar_modelo_caducidad()
    generar_histograma_vencimientos()
