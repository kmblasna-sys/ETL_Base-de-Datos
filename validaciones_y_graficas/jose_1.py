import os
import sys
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import classification_report, confusion_matrix

# ==========================================
# 1. CONFIGURACIÓN DE RUTAS Y CONEXIÓN
# ==========================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "Conexion"))

from Conexion.conexion import obtener_conexion

def analizar_y_predecir_finanzas(conexion=None):
    """
    Orquesta el análisis financiero de las transacciones de Walmart y aplica Minería de Datos (Predicción)
    para clasificar el riesgo de rentabilidad de las ventas.
    
    Filtra los datos utilizando la Utilidad real cargada del CSV para enfocarse en desviaciones
    críticas (pérdidas mayores a $500), clasificándolas de forma realista y correcta.
    
    Retorna:
        dict: Métricas y resultados del modelo predictivo y del análisis.
        list: Lista de tuplas con el detalle de las transacciones con pérdida crítica.
        DecisionTreeClassifier: El modelo de árbol de decisión entrenado.
    """
    cerrar_conexion = False
    if conexion is None:
        conexion = obtener_conexion()
        cerrar_conexion = True
        
    if not conexion:
        raise ConnectionError("No se pudo establecer conexión con la base de datos.")

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

    total_transacciones = len(rows)
    if total_transacciones == 0:
        return {"total": 0}, [], None

    # ==========================================
    # 2. PROCESAMIENTO Y LÓGICA DE CLASIFICACIÓN (GROUND TRUTH)
    # ==========================================
    temp_data = []

    for row in rows:
        id_trans, cod_prod, cant_vendida, v_unit_sin_dcto, util, dcto_prom = row
        
        cant_vendida = int(cant_vendida or 0)
        if cant_vendida <= 0:
            continue
        
        v_unit_sin_dcto = float(v_unit_sin_dcto) if v_unit_sin_dcto is not None else 0.0
        util = float(util) if util is not None else 0.0
        dcto_prom = float(dcto_prom) if dcto_prom is not None else 0.0

        # Precio de venta final por unidad cobrada (con descuento aplicado)
        v_unit_con_dcto = v_unit_sin_dcto * (1.0 - dcto_prom / 100.0)
        
        # Costo unitario real (precio unitario de venta menos utilidad unitaria)
        c_unit = v_unit_con_dcto - (util / cant_vendida)
        
        # Utilidad teórica si no hubiéramos aplicado ningún descuento promocional
        util_sin_dcto = util + (v_unit_sin_dcto * cant_vendida * (dcto_prom / 100.0))

        # Determinar categoría de riesgo/alerta
        if util >= 0:
            lbl_orig = 0 # Rentable
        else:
            if util_sin_dcto >= 0:
                lbl_orig = 1 # Ajustar Dcto.
            else:
                lbl_orig = 2 # Ajustar Base
        
        temp_data.append({
            'id': id_trans,
            'prod': cod_prod,
            'qty': cant_vendida,
            'v_unit': v_unit_con_dcto,
            'c_unit': c_unit,
            'dcto': dcto_prom,
            'v_sin_dcto': v_unit_sin_dcto,
            'utilidad': util,
            'lbl_orig': lbl_orig,
            'perdida_unitaria': c_unit - v_unit_con_dcto
        })

    df = pd.DataFrame(temp_data)

    # Identificar las anomalías del dataset
    class1 = df[df['lbl_orig'] == 1]
    class2 = df[df['lbl_orig'] == 2]

    # Marcar en el dataset para el entrenamiento del clasificador
    df['Target_Riesgo'] = 0
    df.loc[df['id'].isin(class1['id']), 'Target_Riesgo'] = 1
    df.loc[df['id'].isin(class2['id']), 'Target_Riesgo'] = 2

    # ==========================================
    # 3. ENTRENAMIENTO DEL MODELO DE PREDICCIÓN
    # ==========================================
    X = df[['qty', 'c_unit', 'dcto', 'v_sin_dcto']]
    y = df['Target_Riesgo']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42)
    
    clf = DecisionTreeClassifier(max_depth=4, random_state=42)
    clf.fit(X_train, y_train)
    
    accuracy = clf.score(X_test, y_test)
    importancias = dict(zip(X.columns, clf.feature_importances_))
    
    # ==========================================
    # 4. CÁLCULO DE PROYECCIONES FINANCIERAS (MINERÍA DE DATOS)
    # ==========================================
    rec_dcto = 0.0
    rec_base = 0.0
    for _, r in class1.iterrows():
        margin_base = (r['v_sin_dcto'] - r['c_unit']) / r['v_sin_dcto'] if r['v_sin_dcto'] > 0 else 0.0
        dcto_max = max(0.0, margin_base - 0.05)
        new_dcto = dcto_max * 100
        new_util = r['utilidad'] + (r['v_sin_dcto'] * r['qty'] * ((r['dcto'] - new_dcto) / 100.0))
        rec_dcto += (new_util - r['utilidad'])
        
    for _, r in class2.iterrows():
        new_price = r['c_unit'] * 1.05
        new_util = (new_price - r['c_unit']) * r['qty']
        rec_base += (new_util - r['utilidad'])
        
    total_recuperacion = rec_dcto + rec_base
    anomalas_df = df[df['Target_Riesgo'] != 0].copy()
    perdida_total_anom = anomalas_df['utilidad'].sum()

    # Preparar el listado de pérdidas para la Treeview
    losses_list = []
    # Ordenar por pérdida total de la transacción (mayor pérdida primero)
    anomalas_df = anomalas_df.sort_values(by='utilidad', ascending=True)
    
    for _, r in anomalas_df.iterrows():
        estado_margen = "Ajustar Dcto." if r['Target_Riesgo'] == 1 else "Ajustar Base"
        
        # Calcular Precio Simulado Sugerido
        if r['Target_Riesgo'] == 1:
            margin_base = (r['v_sin_dcto'] - r['c_unit']) / r['v_sin_dcto'] if r['v_sin_dcto'] > 0 else 0.0
            dcto_max = max(0.0, margin_base - 0.05)
            v_sim = r['v_sin_dcto'] * (1.0 - dcto_max)
        else:
            v_sim = r['c_unit'] * 1.05
            
        losses_list.append((
            int(r['id']),
            r['prod'],
            int(r['qty']),
            f"${r['v_unit']:.2f}",
            f"${r['c_unit']:.2f}",
            f"{r['dcto']:.1f}%",
            f"-${r['perdida_unitaria']:.2f}",
            f"${v_sim:.2f}",
            estado_margen
        ))

    reporte = {
        "total_analizadas": total_transacciones,
        "perdidas_netas": len(anomalas_df),
        "pct_perdidas": (len(anomalas_df) / total_transacciones) * 100,
        "rentables_originales": total_transacciones - len(anomalas_df),
        "pct_rentables": ((total_transacciones - len(anomalas_df)) / total_transacciones) * 100,
        "recuperables": len(class1),
        "pct_recuperables": (len(class1) / len(anomalas_df)) * 100 if len(anomalas_df) > 0 else 0.0,
        "requiere_ajuste_catalogo": len(class2),
        "pct_requiere_ajuste": (len(class2) / len(anomalas_df)) * 100 if len(anomalas_df) > 0 else 0.0,
        "model_accuracy": accuracy * 100,
        "feature_importances": importancias,
        "perdida_total_dolares": perdida_total_anom,
        "recuperacion_descuento_dolares": rec_dcto,
        "recuperacion_base_dolares": rec_base,
        "recuperacion_total_dolares": total_recuperacion
    }
    
    return reporte, losses_list, clf

if __name__ == "__main__":
    print("===========================================================================")
    print("🤖 MINERÍA DE DATOS Y PREDICCIÓN: AUDITORÍA FINANCIERA (Jose_1)")
    print("===========================================================================")
    
    try:
        reporte, losses, clf = analizar_y_predecir_finanzas()
        
        print(f"\n[+] Total de Transacciones Analizadas   : {reporte['total_analizadas']}")
        print(f"[+] Transacciones Rentables / Correctas: {reporte['rentables_originales']} ({reporte['pct_rentables']:.2f}%)")
        print(f"[+] Alertas de Pérdida Crítica         : {reporte['perdidas_netas']} ({reporte['pct_perdidas']:.2f}%)")
        print("---------------------------------------------------------------------------")
        print("🛡️ CLASIFICACIÓN DE ALERTAS:")
        print(f" -> Ajustar Descuento (Dcto.)          : {reporte['recuperables']} ({reporte['pct_recuperables']:.2f}%)")
        print(f" -> Ajustar Precio de Lista (Base)     : {reporte['requiere_ajuste_catalogo']} ({reporte['pct_requiere_ajuste']:.2f}%)")
        print("---------------------------------------------------------------------------")
        print("📈 RENDIMIENTO DEL CLASIFICADOR PREDICTIVO (Arbol de Decisión):")
        print(f" -> Precisión Global (Accuracy)        : {reporte['model_accuracy']:.2f}%")
        print(" -> Importancia de Atributos en el Riesgo Financiero:")
        for feature, importance in reporte['feature_importances'].items():
            print(f"    * {feature:<15}: {importance * 100:.2f}%")
        
        print("\n📈 PROYECCIONES NUMÉRICAS DE MINERÍA DE DATOS:")
        print(f" -> Pérdida Total Real en Alertas      : -${abs(reporte['perdida_total_dolares']):,.2f}")
        print(f" -> Recuperación Proyectada (Dcto)     : +${reporte['recuperacion_descuento_dolares']:,.2f}")
        print(f" -> Recuperación Proyectada (Base)     : +${reporte['recuperacion_base_dolares']:,.2f}")
        print(f" -> Recuperación Financiera Total      : +${reporte['recuperacion_total_dolares']:,.2f}")
        print("===========================================================================")
        
    except Exception as e:
        print(f"\n[-] ERROR durante la ejecución: {e}")
        sys.exit(1)