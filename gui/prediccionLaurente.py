import os
import sys
import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = None
    np = None

try:
    from validaciones_y_graficas.validacion import obtener_lotes_perecederos
except Exception:
    obtener_lotes_perecederos = None

try:
    from xgboost import XGBClassifier
except Exception:
    XGBClassifier = None


def calcular_metricas(y_true, y_pred, y_prob=None):
    if len(y_true) == 0:
        return {'accuracy': 0.0, 'precision': 0.0, 'recall': 0.0, 'f1': 0.0, 'roc_auc': 0.0}

    accuracy = (sum(1 for a, b in zip(y_true, y_pred) if a == b) / len(y_true)) if len(y_true) else 0.0
    tp = sum(1 for a, b in zip(y_true, y_pred) if a == 1 and b == 1)
    fp = sum(1 for a, b in zip(y_true, y_pred) if a == 0 and b == 1)
    fn = sum(1 for a, b in zip(y_true, y_pred) if a == 1 and b == 0)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    roc_auc = 0.0

    if y_prob is not None and len(y_prob) == len(y_true):
        try:
            from sklearn.metrics import roc_auc_score
            roc_auc = roc_auc_score(y_true, y_prob)
        except Exception:
            roc_auc = 0.0

    return {
        'accuracy': round(accuracy, 4),
        'precision': round(precision, 4),
        'recall': round(recall, 4),
        'f1': round(f1, 4),
        'roc_auc': round(roc_auc, 4),
    }


def preparar_datos_modelo(datos, fecha_referencia=None):
    """
    Construye el DataFrame de entrenamiento.

    IMPORTANTE sobre la etiqueta (riesgo_merma):
    - Si el registro trae 'Fue_Merma' (histórico real de mermas desde la BD),
      se usa esa etiqueta real. En ese caso 'dias_restantes' SÍ puede usarse
      como feature porque no hay relación determinística con el target.
    - Si no existe histórico real, se cae de vuelta a una etiqueta heurística
      (dias_restantes <= 90). Esta heurística NO debe usarse junto con
      'dias_restantes' como feature del mismo modelo, porque el target se
      construye directamente a partir de esa columna: el modelo aprendería
      la regla en vez de un patrón real, y por eso las métricas salían 100%.
      Por eso se marca el origen de la etiqueta en 'etiqueta_origen' y el
      entrenamiento decide qué columnas usar según ese origen.
    """
    if pd is None:
        raise ImportError('pandas no está disponible')

    if fecha_referencia is None:
        fecha_referencia = datetime.datetime.now()
    if isinstance(fecha_referencia, str):
        fecha_referencia = datetime.datetime.fromisoformat(fecha_referencia)

    registros = []
    for fila in datos:
        fecha_ingreso = fila.get('Fecha_ingreso')
        if isinstance(fecha_ingreso, str):
            try:
                fecha_ingreso = datetime.datetime.fromisoformat(fecha_ingreso)
            except Exception:
                fecha_ingreso = None

        vida_util = fila.get('Vida_Util', '2 años')
        try:
            anos = float(str(vida_util).strip().split()[0])
        except Exception:
            anos = 2.0

        if fecha_ingreso:
            fecha_vencimiento = fecha_ingreso + datetime.timedelta(days=int(round(anos * 365)))
            dias_restantes = (fecha_vencimiento - fecha_referencia).days
        else:
            fecha_vencimiento = fecha_referencia
            dias_restantes = -1

        capacidad = float(fila.get('Capacidad_Total', 0) or 0)
        ocupado = float(fila.get('Espacio_ocupado', 0) or 0)
        ratio_uso = (ocupado / capacidad) if capacidad else 0.0

        fue_merma_real = fila.get('Fue_Merma')
        if fue_merma_real is not None:
            etiqueta_origen = 'real'
            riesgo_merma = int(bool(fue_merma_real))
        else:
            etiqueta_origen = 'heuristico'
            riesgo_merma = 1 if dias_restantes <= 90 else 0

        registros.append({
            'Numero_Lote': fila.get('Numero_Lote'),
            'Codigo_de_Producto': fila.get('Codigo_de_Producto'),
            'Nombre_Producto': fila.get('Nombre_Producto', fila.get('Nombre', '')),
            'dias_restantes': dias_restantes,
            'ratio_uso': round(ratio_uso, 4),
            'capacidad_total': capacidad,
            'espacio_ocupado': ocupado,
            'riesgo_merma': riesgo_merma,
            'etiqueta_origen': etiqueta_origen,
        })

    df = pd.DataFrame(registros)

    # Red de seguridad: si por alguna razón llegan lotes duplicados (por ejemplo
    # porque la fuente de datos une con ventas y repite el mismo lote una vez
    # por cada venta histórica), se conserva solo una fila por Numero_Lote.
    # Entrenar con lotes duplicados infla el tamaño de la muestra sin aportar
    # información nueva y sesga el modelo hacia los productos más vendidos.
    if 'Numero_Lote' in df.columns and df['Numero_Lote'].notna().any():
        antes = len(df)
        df = df.drop_duplicates(subset=['Numero_Lote'], keep='first').reset_index(drop=True)
        despues = len(df)
        if despues < antes:
            print(f"[aviso] Se eliminaron {antes - despues} filas duplicadas por Numero_Lote "
                  f"({antes} -> {despues} lotes únicos).")

    return df


def obtener_columnas_features(df):
    """
    Decide qué columnas puede usar el modelo sin fuga de datos.
    Si TODAS las etiquetas vienen de histórico real ('real'), dias_restantes
    es una feature legítima. Si alguna etiqueta es heurística (construida a
    partir de dias_restantes), esa columna se excluye para evitar que el
    modelo simplemente re-descubra la regla con la que armamos el target.
    """
    if 'etiqueta_origen' not in df.columns or df.empty:
        return ['ratio_uso', 'capacidad_total', 'espacio_ocupado']

    origenes = set(df['etiqueta_origen'].unique())
    if origenes == {'real'}:
        return ['dias_restantes', 'ratio_uso', 'capacidad_total', 'espacio_ocupado']
    return ['ratio_uso', 'capacidad_total', 'espacio_ocupado']


def detectar_fuga_datos(df, columnas_features, columna_target='riesgo_merma', umbral=0.97):
    """
    Señal de alerta adicional: si alguna feature todavía queda casi perfectamente
    correlacionada con el target, probablemente sigue habiendo fuga de datos
    (por ejemplo si en el futuro se agregan más columnas derivadas del mismo
    criterio con el que se etiquetó el riesgo).
    """
    alertas = []
    for col in columnas_features:
        if col not in df.columns or df[col].nunique() < 2:
            continue
        try:
            correlacion = df[[col, columna_target]].corr().iloc[0, 1]
        except Exception:
            continue
        if pd.notna(correlacion) and abs(correlacion) >= umbral:
            alertas.append(f"{col} (corr={correlacion:.2f})")
    return alertas


def evaluar_con_cv_repetida(estimator_factory, X, y, n_splits, n_repeats=5, random_state=42):
    """
    Corre validación cruzada varias veces (con distintas particiones aleatorias
    cada vez) y devuelve una lista de métricas, una por repetición.

    Con datasets chicos, un solo StratifiedKFold puede darte un número que en
    realidad depende de qué registros cayeron en cada partición (ruido), no de
    qué tan bueno es el modelo. Repetir la partición varias veces y mirar la
    media y la desviación estándar es mucho más honesto que un solo número.
    """
    from sklearn.model_selection import StratifiedKFold

    resultados_por_repeticion = []
    y_arr = y.reset_index(drop=True)
    X_arr = X.reset_index(drop=True)

    for repeticion in range(n_repeats):
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state + repeticion)
        pred = [None] * len(y_arr)
        prob = [None] * len(y_arr)

        for train_idx, test_idx in cv.split(X_arr, y_arr):
            modelo = estimator_factory()
            modelo.fit(X_arr.iloc[train_idx], y_arr.iloc[train_idx])
            pred_fold = modelo.predict(X_arr.iloc[test_idx])
            prob_fold = modelo.predict_proba(X_arr.iloc[test_idx])[:, 1]
            for pos, idx in enumerate(test_idx):
                pred[idx] = int(pred_fold[pos])
                prob[idx] = float(prob_fold[pos])

        metricas = calcular_metricas(list(y_arr), pred, prob)
        resultados_por_repeticion.append(metricas)

    return resultados_por_repeticion


def resumir_metricas_cv(resultados_por_repeticion):
    """Convierte la lista de métricas por repetición en {clave: (media, desviacion_estandar)}."""
    claves = resultados_por_repeticion[0].keys()
    resumen = {}
    for clave in claves:
        valores = [r[clave] for r in resultados_por_repeticion]
        resumen[clave] = (float(np.mean(valores)), float(np.std(valores)))
    return resumen


def formatear_metricas_media_std(resumen, etiquetas=(('accuracy', 'Accuracy'), ('precision', 'Precision'), ('recall', 'Recall'), ('f1', 'F1'), ('roc_auc', 'ROC-AUC'))):
    partes = []
    for clave, nombre in etiquetas:
        media, std = resumen[clave]
        partes.append(f"{nombre}={media:.2%} (±{std:.2%})")
    return " | ".join(partes)


class PrediccionLaurenteApp:
    def __init__(self, root):
        self.root = root
        self.root.title('Predicción de Merma - Laurente')
        self.root.geometry('1200x760')
        self.root.minsize(1080, 680)

        self.df = pd.DataFrame()
        self.modelo = None
        self.columnas_features = []
        self.resultados = []
        self.metricas = None

        self.crear_layout()

    def crear_layout(self):
        header = tb.Frame(self.root, bootstyle=PRIMARY, padding=12)
        header.pack(fill=X, side=TOP)
        tb.Label(header, text='🔮 Predicción de riesgo de merma por lote', font=('Helvetica', 14, 'bold'), foreground='white').pack(side=LEFT)
        tb.Button(header, text='🔄 Cargar datos', bootstyle='light', command=self.cargar_datos).pack(side=RIGHT)

        controles = tb.Frame(self.root, padding=10)
        controles.pack(fill=X)
        tb.Label(controles, text='Fecha de simulación:', width=18).pack(side=LEFT)
        self.ent_fecha = tb.Entry(controles, width=18)
        self.ent_fecha.insert(0, datetime.datetime.now().strftime('%Y-%m-%d'))
        self.ent_fecha.pack(side=LEFT, padx=(0, 10))
        tb.Label(controles, text='(¿Qué pasaría si hoy fuera esta fecha?)', font=('Helvetica', 9), foreground='#6c757d').pack(side=LEFT, padx=(0, 10))
        tb.Button(controles, text='Entrenar modelo', bootstyle='success', command=self.entrenar_modelo).pack(side=LEFT)
        tb.Button(controles, text='Analizar riesgo', bootstyle='info', command=self.analizar_riesgo).pack(side=LEFT, padx=(10, 0))

        panel = tb.Frame(self.root, padding=12)
        panel.pack(fill=BOTH, expand=YES)

        self.tree = tb.Treeview(panel, columns=('lote', 'producto', 'dias_restantes', 'ratio_uso', 'probabilidad', 'riesgo'), show='headings', bootstyle='secondary', height=18)
        for col, text, width in [
            ('lote', 'Lote', 120),
            ('producto', 'Producto', 260),
            ('dias_restantes', 'Días restantes', 120),
            ('ratio_uso', 'Ratio de uso', 120),
            ('probabilidad', 'Prob. de merma', 140),
            ('riesgo', 'Riesgo', 120),
        ]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor=W)
        self.tree.pack(fill=BOTH, expand=YES, side=LEFT)

        scroll_y = tb.Scrollbar(panel, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side=LEFT, fill=Y)

        self.lbl_estado = tb.Label(self.root, text='Estado: listo para cargar datos.', font=('Helvetica', 10))
        self.lbl_estado.pack(anchor=W, padx=12, pady=(0, 12))

        self.lbl_metricas = tb.Label(self.root, text='Métricas: aún no hay entrenamiento.', font=('Helvetica', 10), bootstyle='info', wraplength=900)
        self.lbl_metricas.pack(anchor=W, padx=12, pady=(0, 6))

        frame_resumen = tb.Frame(self.root)
        frame_resumen.pack(fill=X, padx=12, pady=(0, 6))

        self.txt_resumen = tk.Text(frame_resumen, height=14, width=120, wrap='word')
        self.txt_resumen.pack(side=LEFT, fill=X, expand=YES)
        scroll_resumen = tb.Scrollbar(frame_resumen, orient=VERTICAL, command=self.txt_resumen.yview)
        self.txt_resumen.configure(yscrollcommand=scroll_resumen.set)
        scroll_resumen.pack(side=LEFT, fill=Y)
        self.txt_resumen.insert('1.0', 'Resumen de evaluación: aún no hay datos.')
        self.txt_resumen.config(state='disabled')

    def cargar_datos(self):
        if obtener_lotes_perecederos is None:
            messagebox.showwarning('Datos', 'No se encontró la función de validación. Verifica validacion.py.')
            return

        datos = obtener_lotes_perecederos()
        if not datos:
            messagebox.showwarning('Datos', 'No se encontraron lotes para analizar.')
            return

        self.df = preparar_datos_modelo(datos, fecha_referencia=self.ent_fecha.get())
        self.modelo = None
        self.columnas_features = []
        self.lbl_estado.config(text=f'Datos cargados: {len(self.df)} lotes.')
        self.lbl_metricas.config(text='Métricas: aún no hay entrenamiento.')
        self.txt_resumen.config(state='normal')
        self.txt_resumen.delete('1.0', 'end')
        self.txt_resumen.insert('1.0', 'Resumen de evaluación: aún no hay datos.')
        self.txt_resumen.config(state='disabled')
        self.mostrar_resultados([])

    def entrenar_modelo(self):
        if self.df.empty:
            messagebox.showwarning('Modelo', 'Primero carga los datos.')
            return

        if XGBClassifier is None:
            messagebox.showerror('Modelo', 'XGBoost no está instalado. Instálalo con: pip install xgboost')
            return

        if len(self.df) < 10:
            messagebox.showwarning('Modelo', 'Se necesitan al menos 10 registros para obtener una evaluación confiable.')
            return

        try:
            from sklearn.model_selection import StratifiedKFold, RandomizedSearchCV
            from sklearn.linear_model import LogisticRegression
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
        except ImportError:
            messagebox.showerror('Modelo', 'scikit-learn no está instalado. Instálalo con: pip install scikit-learn')
            return

        columnas_features = obtener_columnas_features(self.df)
        X = self.df[columnas_features]
        y = self.df['riesgo_merma']

        if y.nunique() < 2:
            messagebox.showwarning(
                'Modelo',
                'Todos los lotes cargados pertenecen a la misma clase de riesgo. '
                'Se necesitan lotes en riesgo y lotes normales para poder entrenar y evaluar un clasificador.'
            )
            return

        conteo_clases = y.value_counts()
        n_splits = min(5, int(conteo_clases.min()))
        if n_splits < 2:
            messagebox.showwarning(
                'Modelo',
                'La clase minoritaria tiene muy pocos registros para una validación cruzada confiable. '
                'Agrega más datos de lotes en riesgo o normales.'
            )
            return

        alertas_fuga = detectar_fuga_datos(self.df, columnas_features)

        self.lbl_estado.config(text='Entrenando y evaluando... esto puede tardar unos segundos (baseline + búsqueda de hiperparámetros + validación cruzada repetida).')
        self.root.update_idletasks()

        # --- 1) Línea base: regresión logística. No puede memorizar reglas raras,
        # así que si da métricas parecidas a XGBoost, es buena señal de que hay
        # patrón real y no solo un modelo complejo aprovechando ruido. ---
        cv_busqueda = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

        resultados_baseline = evaluar_con_cv_repetida(
            lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=42)),
            X, y, n_splits=n_splits, n_repeats=5, random_state=42,
        )
        resumen_baseline = resumir_metricas_cv(resultados_baseline)

        # --- 2) Búsqueda de hiperparámetros para XGBoost (en vez de ajustarlos
        # a mano/al ojo). Se hace sobre los mismos folds de CV. ---
        param_dist = {
            'n_estimators': [50, 80, 120, 160, 200],
            'max_depth': [2, 3, 4, 5, 6],
            'learning_rate': [0.03, 0.05, 0.08, 0.12, 0.2],
            'subsample': [0.7, 0.8, 0.9, 1.0],
            'colsample_bytree': [0.7, 0.8, 0.9, 1.0],
        }
        base_xgb = XGBClassifier(random_state=42, eval_metric='logloss')
        busqueda = RandomizedSearchCV(
            base_xgb,
            param_distributions=param_dist,
            n_iter=20,
            scoring='f1',
            cv=cv_busqueda,
            random_state=42,
            n_jobs=-1 if len(self.df) >= 30 else 1,
        )
        busqueda.fit(X, y)
        mejores_parametros = busqueda.best_params_

        # --- 3) Con los hiperparámetros ya elegidos, se evalúa de nuevo con CV
        # repetida (separado de la búsqueda) para tener una métrica fuera de
        # muestra que no esté contaminada por el propio proceso de selección. ---
        resultados_xgb = evaluar_con_cv_repetida(
            lambda: XGBClassifier(random_state=42, eval_metric='logloss', **mejores_parametros),
            X, y, n_splits=n_splits, n_repeats=5, random_state=42,
        )
        resumen_xgb = resumir_metricas_cv(resultados_xgb)

        # Métrica "headline" que se muestra arriba (media de la CV repetida de XGBoost)
        self.metricas = {clave: media for clave, (media, _std) in resumen_xgb.items()}

        # --- 4) Modelo final: se entrena con TODOS los datos y con los mejores
        # hiperparámetros. Es el que se usa después en "Analizar riesgo". ---
        modelo_final = XGBClassifier(random_state=42, eval_metric='logloss', **mejores_parametros)
        modelo_final.fit(X, y)
        self.modelo = modelo_final
        self.columnas_features = columnas_features

        # --- 5) Importancia de features del modelo final ---
        importancias = sorted(
            zip(columnas_features, modelo_final.feature_importances_),
            key=lambda par: par[1],
            reverse=True,
        )

        origenes = set(self.df['etiqueta_origen'].unique())
        if origenes == {'real'}:
            origen_label = 'histórica (columna Fue_Merma de la base de datos)'
        else:
            origen_label = 'heurística (dias_restantes <= 90, por no existir aún histórico real de mermas)'

        self.lbl_estado.config(
            text=f'Modelo entrenado con XGBoost (hiperparámetros ajustados por búsqueda) sobre {n_splits} particiones x 5 repeticiones. '
                 f'Origen de la etiqueta: {origen_label}.'
        )
        self.lbl_metricas.config(
            text='XGBoost (CV repetida): ' + formatear_metricas_media_std(resumen_xgb)
        )

        texto_resumen = (
            'Resumen de evaluación (validación cruzada repetida: 5 repeticiones x '
            f'{n_splits} particiones, siempre sobre datos fuera de muestra)\n\n'
            f"- Columnas usadas como features: {', '.join(columnas_features)}\n\n"
            f"Línea base (Regresión logística):\n  {formatear_metricas_media_std(resumen_baseline)}\n\n"
            f"XGBoost (hiperparámetros ajustados con RandomizedSearchCV, scoring='f1'):\n  {formatear_metricas_media_std(resumen_xgb)}\n\n"
            f"Mejores hiperparámetros encontrados: {mejores_parametros}\n\n"
            "Importancia de features (XGBoost, modelo final):\n"
            + "\n".join(f"  - {nombre}: {valor:.3f}" for nombre, valor in importancias)
        )

        if origenes != {'real'}:
            texto_resumen += (
                "\n\nNota: 'dias_restantes' se excluyó de las features porque la etiqueta heurística "
                "se construye a partir de esa misma columna (dias_restantes <= 90). Usarla como "
                "feature y como base del target al mismo tiempo es lo que causaba el 100% artificial."
            )

        diferencia_f1 = resumen_xgb['f1'][0] - resumen_baseline['f1'][0]
        if diferencia_f1 < 0.03:
            texto_resumen += (
                "\n\n⚠ XGBoost apenas supera (o no supera) a la regresión logística en F1. "
                "Esto sugiere que hay poca señal real más allá de una relación simple entre las "
                "features y el riesgo, o que faltan variables con más poder predictivo."
            )

        if alertas_fuga:
            texto_resumen += (
                "\n\n⚠ Advertencia de posible fuga de datos: las siguientes columnas siguen teniendo "
                f"correlación casi perfecta con la etiqueta: {', '.join(alertas_fuga)}. Revisa si deberían excluirse."
            )

        self.txt_resumen.config(state='normal')
        self.txt_resumen.delete('1.0', 'end')
        self.txt_resumen.insert('1.0', texto_resumen)
        self.txt_resumen.config(state='disabled')

    def analizar_riesgo(self):
        if self.df.empty:
            messagebox.showwarning('Análisis', 'Primero carga los datos.')
            return
        if self.modelo is None:
            messagebox.showwarning('Análisis', 'Entrena el modelo antes de predecir.')
            return

        columnas_features = self.columnas_features or obtener_columnas_features(self.df)
        X = self.df[columnas_features]
        probabilidades = self.modelo.predict_proba(X)[:, 1]
        self.df['probabilidad_merma'] = probabilidades
        self.df['riesgo_predicho'] = self.df['probabilidad_merma'].apply(lambda p: 'Alto' if p >= 0.6 else 'Medio' if p >= 0.3 else 'Bajo')

        self.mostrar_resultados(self.df)
        self.lbl_estado.config(text='Análisis completado. Se muestra la probabilidad estimada de merma.')

    def mostrar_resultados(self, resultados):
        for item in self.tree.get_children():
            self.tree.delete(item)

        if isinstance(resultados, pd.DataFrame):
            datos = resultados.to_dict('records')
        else:
            datos = resultados

        for fila in datos:
            if isinstance(fila, dict):
                lote = fila.get('Numero_Lote', '-')
                producto = fila.get('Nombre_Producto', '-')
                dias = fila.get('dias_restantes', '-')
                ratio = fila.get('ratio_uso', '-')
                prob = fila.get('probabilidad_merma', '-')
                riesgo = fila.get('riesgo_predicho', fila.get('riesgo_merma', '-'))
                if isinstance(prob, float):
                    prob = f'{prob:.2%}'
                if isinstance(ratio, float):
                    ratio = f'{ratio:.2%}'
                if isinstance(dias, int):
                    dias = str(dias)
                self.tree.insert('', 'end', values=(lote, producto, dias, ratio, prob, riesgo))


if __name__ == '__main__':
    root = tb.Window(themename='litera')
    app = PrediccionLaurenteApp(root)
    root.mainloop()