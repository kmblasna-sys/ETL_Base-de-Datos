"""
Panel de Simulación y Control de Ofertas Vigentes
--------------------------------------------------
Módulo: panel_simulacion_ofertas.py
Proyecto: Auditoría y Simulación Promocional - Walmart (Mineria_BD)

Componentes:
1. Cronograma visual (Gantt) de las campañas activas, resaltando en rojo
   las promociones que ya presentan traslape (misma lógica de la Regla 1).
   Incluye un selector "Histórico completo" / "Vigentes hoy": el dataset
   del proyecto es un histórico 2020-2023, así que "Vigentes hoy" sirve
   para diferenciar el estado de negocio (Estado_Promocion = 'Activa',
   que es un flag dentro del dataset) de la vigencia real en el
   calendario (CURDATE() dentro del rango Fecha_Inicio/Fecha_Finalizacion).
2. Simulador de ofertas: antes de registrar una nueva promoción, cruza el
   rango propuesto contra Prod_Prom/PROMOCION para detectar traslapes y
   estima si el margen resultante caería bajo el 5% mínimo.
"""

import sys
import os
import tkinter as tk
import matplotlib.dates as mdates
from datetime import date, datetime, timedelta

# [CORRECCIÓN DPI EN WINDOWS]
# Sin esto, en pantallas con escalado (125%/150%, muy común en laptops),
# Windows re-escala la ventana de Tkinter sin que la app lo sepa, y el
# contenido termina renderizándose más ancho de lo reportado, empujando
# paneles fuera del área visible. Debe ejecutarse ANTES de crear cualquier
# ventana.
if sys.platform.startswith("win"):
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split

# [CONFIGURACIÓN DE RUTAS Y CONEXIÓN]
# Se busca la carpeta "Conexion" subiendo por los directorios padre en lugar
# de asumir una profundidad fija, ya que esta varía según dónde se guarde
# este archivo dentro del proyecto (por ejemplo codigo_bd/codigo_bd/ vs.
# codigo_bd/codigo_bd/Paneles/).
def _agregar_ruta_conexion():
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        candidato = os.path.join(directorio_actual, "Conexion")
        if os.path.isdir(candidato):
            sys.path.append(candidato)
            sys.path.append(directorio_actual)
            return
        directorio_actual = os.path.dirname(directorio_actual)
    raise ImportError(
        "No se encontró la carpeta 'Conexion' subiendo desde "
        f"{os.path.dirname(os.path.abspath(__file__))}. "
        "Verifica dónde está guardado conexion.py."
    )


_agregar_ruta_conexion()
from Conexion.conexion import obtener_conexion


class PanelSimulacionOfertas(ttk.Frame):
    """Panel de simulación y control de ofertas vigentes."""

    def __init__(self, contenedor_padre):
        super().__init__(contenedor_padre)
        self.pack(fill=BOTH, expand=True)

        # 1. Creamos AMBOS contenedores primero
        self.frame_cronograma = ttk.Labelframe(
            self, text="Cronograma de Campañas Activas", padding=10
        )
        self.frame_simulador = ttk.Labelframe(
            self, text="Simulador de Nueva Oferta", padding=10
        )

        # 2. Empaquetamos PRIMERO el simulador a la derecha
        self.frame_simulador.pack(side=RIGHT, fill=Y, padx=10, pady=10)

        # 3. Empaquetamos al FINAL el cronograma para que tome TODO el
        #    espacio restante a la izquierda
        self.frame_cronograma.pack(side=LEFT, fill=BOTH, expand=True, padx=10, pady=10)

        self._oferta_validada = None
        self._modelo_riesgo = None
        self._modelo_accuracy = 0.0
        self.modo_vista = tk.StringVar(value="historico")

        # Entrena el árbol de decisión predictivo al iniciar el panel
        self._entrenar_modelo_predictivo()

        # Primero se construye el simulador (así frame_simulador ya tiene su
        # ancho REAL, con sus Entry/Combobox adentro, antes de que se calcule
        # cuánto espacio le queda al cronograma).
        self._construir_formulario_simulador()

        # update() COMPLETO (no update_idletasks): fuerza a Tkinter a negociar
        # y aplicar la geometría final con el gestor de ventanas ANTES de medir
        # frame_cronograma. update_idletasks() no basta la primera vez que la
        # ventana se mapea en pantalla; puede seguir reportando un tamaño
        # transitorio (a veces hasta 1x1 px).
        self.winfo_toplevel().update()

        self._construir_controles_cronograma()
        self._construir_cronograma()

    # ------------------------------------------------------------------
    # CRONOGRAMA VISUAL (GANTT)
    # ------------------------------------------------------------------
    def _construir_controles_cronograma(self):
        """Controles fijos del cronograma (no se destruyen al recargar el
        gráfico): el selector de vista y el frame donde vive el gráfico."""
        frame_controles = ttk.Frame(self.frame_cronograma)
        frame_controles.pack(fill=X, pady=(0, 8))

        ttk.Radiobutton(
            frame_controles, text="Histórico completo", variable=self.modo_vista,
            value="historico", command=self._construir_cronograma
        ).pack(side=LEFT, padx=(0, 15))

        ttk.Radiobutton(
            frame_controles, text="Vigentes hoy", variable=self.modo_vista,
            value="vigentes", command=self._construir_cronograma
        ).pack(side=LEFT)

        # Contenedor exclusivo para el gráfico: se limpia y reconstruye cada
        # vez que cambia el selector, sin tocar los Radiobutton de arriba.
        self.frame_grafico = ttk.Frame(self.frame_cronograma)
        self.frame_grafico.pack(fill=BOTH, expand=True)

    def _obtener_promociones_activas(self, solo_vigentes_hoy=False):
        conexion = obtener_conexion()
        if conexion is None:
            return []
        cursor = conexion.cursor()
        query = """
            SELECT Id_promocion, Fecha_Inicio, Fecha_Finalizacion
            FROM PROMOCION
            WHERE Estado_Promocion = 'Activa'
              AND Fecha_Finalizacion >= Fecha_Inicio
        """
        # NOTA: la condición Fecha_Finalizacion >= Fecha_Inicio descarta
        # promociones con fechas invertidas por error de carga en el dataset
        # (ej. Promo 12 y 15 detectadas manualmente). Es un filtro temporal:
        # en cuanto se corrija el dato en Mineria_BD, esas promociones
        # vuelven a aparecer solas, sin tocar este código.
        if solo_vigentes_hoy:
            # Estado_Promocion='Activa' es un flag de negocio dentro del
            # dataset; esto añade el filtro de vigencia real en calendario.
            query += " AND CURDATE() BETWEEN Fecha_Inicio AND Fecha_Finalizacion"
        query += " ORDER BY Fecha_Inicio"
        cursor.execute(query)
        datos = cursor.fetchall()
        cursor.close()
        conexion.close()
        return datos

    def _detectar_traslapes(self, promociones):
        """Marca como conflictivas las promociones cuyo rango se cruza con otra
        (misma condición usada en el self-join sobre Prod_Prom de la Regla 1)."""
        conflictivas = set()
        for i in range(len(promociones)):
            id_a, ini_a, fin_a = promociones[i]
            for j in range(i + 1, len(promociones)):
                id_b, ini_b, fin_b = promociones[j]
                if ini_a <= fin_b and ini_b <= fin_a:
                    conflictivas.add(id_a)
                    conflictivas.add(id_b)
        return conflictivas

    # ------------------------------------------------------------------
    # MODELO PREDICTIVO - ÁRBOL DE DECISIÓN
    # ------------------------------------------------------------------
    def _entrenar_modelo_predictivo(self):
        """Entrena un árbol de decisión con el histórico de ventas para
        predecir la rentabilidad de una oferta antes de registrarla."""
        conexion = obtener_conexion()
        if conexion is None:
            return
        cursor = conexion.cursor()
        try:
            cursor.execute("""
                SELECT
                    dv.Codigo_de_Producto,
                    dv.Cantidad_Adquirida,
                    dv.Precio_Unitario,
                    dv.Utilidad,
                    COALESCE(p.Porcentaje_Descuento, 0.0),
                    pr.id_categoria,
                    COALESCE(DATEDIFF(p.Fecha_Finalizacion, p.Fecha_Inicio), 0)
                FROM DetalleVenta dv
                JOIN Historial_Comercial hc ON dv.Id_Detalle = hc.Id_Historial
                LEFT JOIN PROMOCION p ON hc.Id_promocion = p.Id_promocion
                LEFT JOIN Producto pr ON dv.Codigo_de_Producto = pr.Codigo_de_Producto
            """)
            rows = cursor.fetchall()
        except Exception:
            return
        finally:
            cursor.close()
            conexion.close()

        if not rows or len(rows) < 20:
            return

        registros = []
        for row in rows:
            _, qty, precio_unit, utilidad, descuento, cat_id, duracion = row
            qty = int(qty or 0)
            if qty <= 0:
                continue
            precio_unit = float(precio_unit or 0)
            utilidad = float(utilidad or 0)
            if precio_unit <= 0:
                continue

            descuento = float(descuento or 0)
            cat_id = int(cat_id or 0)
            duracion = int(duracion or 0)

            margen = (utilidad / (precio_unit * qty)) * 100

            registros.append({
                'qty': qty,
                'precio_unit': precio_unit,
                'descuento': descuento,
                'cat_id': cat_id,
                'duracion': duracion,
                'target': 0 if margen >= 5 else 1
            })

        if len(registros) < 20:
            return

        df = pd.DataFrame(registros)
        X = df[['qty', 'precio_unit', 'descuento', 'cat_id', 'duracion']]
        y = df['target']

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        clf = DecisionTreeClassifier(max_depth=4, random_state=42)
        clf.fit(X_train, y_train)

        self._modelo_riesgo = clf
        self._modelo_accuracy = clf.score(X_test, y_test) * 100

    def _predecir_riesgo_oferta(self, descuento, stock, codigo_producto, duracion):
        """Predice si una oferta propuesta tiene riesgo de no ser rentable.

        Retorna:
            tuple: (prediccion, prob_no_rentable)
                - prediccion: 0 (rentable) o 1 (no rentable), None si no hay modelo
                - prob_no_rentable: probabilidad estimada de no ser rentable (0.0-1.0)
        """
        if self._modelo_riesgo is None:
            return None, 0.0

        conexion = obtener_conexion()
        if conexion is None:
            return None, 0.0

        cursor = conexion.cursor()
        try:
            cursor.execute(
                "SELECT id_categoria FROM Producto WHERE Codigo_de_Producto = %s",
                (codigo_producto,)
            )
            fila = cursor.fetchone()
            cat_id = int(fila[0]) if fila else 0

            cursor.execute("""
                SELECT v.Precio_venta
                FROM DetalleVenta dv
                JOIN Venta v ON dv.Numero_Transaccion = v.Numero_Transaccion
                WHERE dv.Codigo_de_Producto = %s
                ORDER BY v.Fecha_Hora_Emision DESC
                LIMIT 1
            """, (codigo_producto,))
            fila = cursor.fetchone()
            precio_unit = float(fila[0]) if fila else 0.0
        except Exception:
            cat_id = 0
            precio_unit = 0.0
        finally:
            cursor.close()
            conexion.close()

        features = pd.DataFrame([{
            'qty': stock,
            'precio_unit': precio_unit,
            'descuento': descuento,
            'cat_id': cat_id,
            'duracion': duracion
        }])

        try:
            proba = self._modelo_riesgo.predict_proba(features)[0]
            pred = self._modelo_riesgo.predict(features)[0]
            prob_no_rentable = proba[1] if len(proba) > 1 else proba[0]
            return int(pred), float(prob_no_rentable)
        except Exception:
            return None, 0.0

    def _mostrar_advisory(self):
        """Muestra el frame de asesoría del modelo predictivo."""
        if not self.frame_advisory.winfo_ismapped():
            self.frame_advisory.pack(fill=X, pady=5, before=self.boton_aprobar)

    def _ocultar_advisory(self):
        """Oculta el frame de asesoría y reinicia el checkbox."""
        self.frame_advisory.pack_forget()
        self.var_acepto_riesgo.set(False)

    def _on_toggle_riesgo(self):
        """Callback del checkbox: habilita/deshabilita el botón de aprobar."""
        if self._oferta_validada is None:
            return
        if self.var_acepto_riesgo.get():
            self.boton_aprobar.config(state="normal")
        else:
            self.boton_aprobar.config(state=DISABLED)

    def _construir_cronograma(self):
        solo_vigentes = self.modo_vista.get() == "vigentes"
        promociones = self._obtener_promociones_activas(solo_vigentes_hoy=solo_vigentes)
        conflictivas = self._detectar_traslapes(promociones)

        # Limpieza manual: solo el frame del gráfico, no los Radiobutton.
        for widget in self.frame_grafico.winfo_children():
            widget.destroy()

        if not promociones:
            mensaje = (
                "No hay promociones vigentes hoy.\n\n"
                "El dataset de este proyecto es histórico (2020-2023),\n"
                "por eso 'Vigentes hoy' no devuelve resultados con estos datos."
                if solo_vigentes else
                "No hay promociones activas en el dataset."
            )
            ttk.Label(
                self.frame_grafico, text=mensaje, justify=CENTER, bootstyle="secondary"
            ).pack(expand=True)
            return

        figura = Figure(figsize=(6, 4.5), dpi=100)
        ax = figura.add_subplot(111)
        ax.margins(x=0)

        todas_las_fechas = []
        for idx, (id_promo, inicio, fin) in enumerate(promociones):
            duracion = (fin - inicio).days
            if duracion <= 0:
                duracion = 1

            todas_las_fechas.extend([inicio, fin])

            color = "#E53935" if id_promo in conflictivas else "#0071CE"
            ax.barh(idx, duracion, left=inicio, height=0.5, color=color, edgecolor="white")
            ax.text(inicio, idx, f"  Promo {id_promo}", va="center", fontsize=8)

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())

        if todas_las_fechas:
            fecha_min = min(todas_las_fechas)
            fecha_max = max(todas_las_fechas)
            margen_derecho = timedelta(days=20)
            ax.set_xlim(fecha_min, fecha_max + margen_derecho)
            ax.set_xbound(lower=fecha_min, upper=fecha_max + margen_derecho)

        figura.autofmt_xdate()

        ax.set_ylim(-0.5, len(promociones) - 0.5)
        ax.set_yticks([])
        ax.set_xlabel("Línea de Tiempo")
        titulo = "Vigentes Hoy" if solo_vigentes else "Histórico Completo"
        ax.set_title(
            f"Cronograma de Campañas ({titulo})\n(rojo = traslape detectado)",
            fontsize=11, fontweight="bold"
        )
        ax.grid(axis="x", linestyle="--", alpha=0.4)
        figura.tight_layout()

        lienzo = FigureCanvasTkAgg(figura, master=self.frame_grafico)
        lienzo.draw()
        lienzo.get_tk_widget().pack(fill=BOTH, expand=True)

    # ------------------------------------------------------------------
    # SIMULADOR DE VALIDACIÓN
    # ------------------------------------------------------------------
    def _obtener_tipos_promocion(self):
        conexion = obtener_conexion()
        if conexion is None:
            return []
        cursor = conexion.cursor()
        cursor.execute("SELECT Id_Tipo, Nombre_Tipo FROM Tipo_Promocion ORDER BY Nombre_Tipo")
        datos = cursor.fetchall()
        cursor.close()
        conexion.close()
        return datos

    def _construir_formulario_simulador(self):
        self._tipos_promocion = self._obtener_tipos_promocion()
        opciones_tipo = [f"{tid} - {nombre}" for tid, nombre in self._tipos_promocion]

        ttk.Label(self.frame_simulador, text="Código de Producto:").pack(anchor=W, pady=(5, 0))
        self.entrada_producto = ttk.Entry(self.frame_simulador)
        self.entrada_producto.pack(fill=X)

        ttk.Label(self.frame_simulador, text="Tipo de Promoción:").pack(anchor=W, pady=(10, 0))
        self.combo_tipo = ttk.Combobox(self.frame_simulador, values=opciones_tipo, state="readonly")
        self.combo_tipo.pack(fill=X)
        if opciones_tipo:
            self.combo_tipo.current(0)

        ttk.Label(self.frame_simulador, text="Fecha Inicio (YYYY-MM-DD):").pack(anchor=W, pady=(10, 0))
        self.entrada_inicio = ttk.Entry(self.frame_simulador)
        self.entrada_inicio.pack(fill=X)

        ttk.Label(self.frame_simulador, text="Fecha Fin (YYYY-MM-DD):").pack(anchor=W, pady=(10, 0))
        self.entrada_fin = ttk.Entry(self.frame_simulador)
        self.entrada_fin.pack(fill=X)

        ttk.Label(self.frame_simulador, text="Descuento Propuesto (%):").pack(anchor=W, pady=(10, 0))
        self.entrada_descuento = ttk.Entry(self.frame_simulador)
        self.entrada_descuento.pack(fill=X)

        ttk.Label(self.frame_simulador, text="Stock Afectado (unidades):").pack(anchor=W, pady=(10, 0))
        self.entrada_stock = ttk.Entry(self.frame_simulador)
        self.entrada_stock.pack(fill=X)

        ttk.Button(
            self.frame_simulador, text="Validar Oferta", bootstyle=PRIMARY,
            command=self._validar_oferta
        ).pack(pady=15, fill=X)

        self.etiqueta_resultado = ttk.Label(
            self.frame_simulador, text="", wraplength=250, justify=LEFT
        )
        self.etiqueta_resultado.pack(fill=X, pady=5)

        self.frame_advisory = ttk.Labelframe(
            self.frame_simulador, text="🤖 Predicción del Modelo Predictivo", padding=8
        )
        self.etiqueta_advisory = ttk.Label(
            self.frame_advisory, text="", wraplength=230, justify=LEFT
        )
        self.etiqueta_advisory.pack(fill=X, pady=(0, 5))
        self.var_acepto_riesgo = tk.BooleanVar(value=False)
        self.check_riesgo = ttk.Checkbutton(
            self.frame_advisory,
            text="Entiendo el riesgo y deseo continuar",
            variable=self.var_acepto_riesgo,
            bootstyle="warning",
            command=self._on_toggle_riesgo
        )
        self.check_riesgo.pack(fill=X)

        self.boton_aprobar = ttk.Button(
            self.frame_simulador, text="Aprobar y Registrar",
            bootstyle=SUCCESS, state=DISABLED, command=self._registrar_oferta
        )
        self.boton_aprobar.pack(pady=10, fill=X)

    def _validar_oferta(self):
        errores = []

        # 1. Recolectar y limpiar entradas
        codigo_producto = self.entrada_producto.get().strip()
        fecha_inicio_str = self.entrada_inicio.get().strip()
        fecha_fin_str = self.entrada_fin.get().strip()
        descuento_raw = self.entrada_descuento.get().strip().replace("%", "")
        stock_raw = self.entrada_stock.get().strip()

        if not all([codigo_producto, fecha_inicio_str, fecha_fin_str, descuento_raw, stock_raw]):
            self.etiqueta_resultado.config(
                text="⚠️ Todos los campos son obligatorios.", bootstyle="danger"
            )
            self.boton_aprobar.config(state=DISABLED)
            self._oferta_validada = None
            return

        # 2. Validación de formato (descuento, stock, fechas)
        descuento_val = None
        stock_val = None
        fecha_inicio_dt = None
        fecha_fin_dt = None

        try:
            descuento_val = float(descuento_raw)
            if not (0 < descuento_val <= 100):
                errores.append("- El descuento debe estar entre 0% y 100%.")
        except ValueError:
            errores.append("- El descuento debe ser un número válido (ej: 20 o 14.5).")

        try:
            stock_val = int(stock_raw)
            if stock_val <= 0:
                errores.append("- El stock afectado debe ser mayor a 0.")
        except ValueError:
            errores.append("- El stock debe ser un número entero (sin letras ni decimales).")

        try:
            fecha_inicio_dt = datetime.strptime(fecha_inicio_str, "%Y-%m-%d").date()
            fecha_fin_dt = datetime.strptime(fecha_fin_str, "%Y-%m-%d").date()
            if fecha_fin_dt < fecha_inicio_dt:
                errores.append("- La fecha de fin no puede ser anterior a la de inicio.")
        except ValueError:
            errores.append("- Formato de fecha incorrecto. Use AAAA-MM-DD (ej: 2026-07-15).")

        if errores:
            self.etiqueta_resultado.config(
                text="⛔ Errores detectados:\n" + "\n".join(errores), bootstyle="danger"
            )
            self.boton_aprobar.config(state=DISABLED)
            self._oferta_validada = None
            return

        # 3. Con el formato ya validado, se cruza contra Mineria_BD:
        #    Regla determinística (traslape + margen) + modelo predictivo.
        conexion = obtener_conexion()
        if conexion is None:
            self.etiqueta_resultado.config(text="⚠ No se pudo conectar a Mineria_BD.", bootstyle="danger")
            self.boton_aprobar.config(state=DISABLED)
            self._oferta_validada = None
            self._ocultar_advisory()
            return
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT p.Id_promocion, p.Fecha_Inicio, p.Fecha_Finalizacion
            FROM Prod_Prom pp
            JOIN PROMOCION p ON pp.Codigo_Promocion = p.Id_promocion
            WHERE pp.Codigo_Producto = %s
              AND p.Estado_Promocion = 'Activa'
              AND p.Fecha_Inicio <= %s
              AND p.Fecha_Finalizacion >= %s
        """, (codigo_producto, fecha_fin_dt, fecha_inicio_dt))
        traslapes = cursor.fetchall()

        cursor.execute("""
            SELECT v.Precio_venta
            FROM DetalleVenta dv
            JOIN Venta v ON dv.Numero_Transaccion = v.Numero_Transaccion
            WHERE dv.Codigo_de_Producto = %s
            ORDER BY v.Fecha_Hora_Emision DESC
            LIMIT 1
        """, (codigo_producto,))
        fila_venta = cursor.fetchone()

        cursor.execute("""
            SELECT c.Precio_Compra
            FROM Detalle_Compra dc
            JOIN Compra c ON dc.Id_Compra = c.Id_Compra
            WHERE dc.Codigo_de_Producto = %s
            ORDER BY c.Fecha_Compra DESC
            LIMIT 1
        """, (codigo_producto,))
        fila_compra = cursor.fetchone()

        cursor.close()
        conexion.close()

        # --- Regla determinística: traslape → bloqueo duro ---
        if traslapes:
            ids_conflicto = ", ".join(str(t[0]) for t in traslapes)
            self.etiqueta_resultado.config(
                text=f"⛔ Oferta rechazada: traslape con promoción(es) activa(s): {ids_conflicto}.",
                bootstyle="danger"
            )
            self.boton_aprobar.config(state=DISABLED)
            self._oferta_validada = None
            self._ocultar_advisory()
            return

        # --- Regla determinística: cálculo de margen ---
        margen_estimado = None
        margen_texto = ""
        if fila_venta and fila_compra:
            precio_venta_base = float(fila_venta[0])
            precio_compra = float(fila_compra[0])
            precio_con_descuento = precio_venta_base * (1 - descuento_val / 100)
            if precio_compra > 0:
                margen_estimado = ((precio_con_descuento - precio_compra) / precio_compra) * 100
                margen_texto = f"{margen_estimado:.2f}%"
        else:
            self.etiqueta_resultado.config(
                text="⛔ No hay historial de venta/compra suficiente para estimar el margen.",
                bootstyle="danger"
            )
            self.boton_aprobar.config(state=DISABLED)
            self._oferta_validada = None
            self._ocultar_advisory()
            return

        # Margen negativo → bloqueo duro (el usuario pierde dinero)
        if margen_estimado < 0:
            self.etiqueta_resultado.config(
                text=f"⛔ Oferta rechazada: margen estimado de {margen_texto} es negativo.",
                bootstyle="danger"
            )
            self.boton_aprobar.config(state=DISABLED)
            self._oferta_validada = None
            self._ocultar_advisory()
            return

        # --- Capa 2: Predicción del árbol de decisión ---
        duracion = (fecha_fin_dt - fecha_inicio_dt).days
        pred_modelo, prob_no_rentable = self._predecir_riesgo_oferta(
            descuento_val, stock_val, codigo_producto, duracion
        )
        modelo_riesgo = (pred_modelo == 1) if pred_modelo is not None else False
        margen_bajo = margen_estimado is not None and margen_estimado < 5

        # Preparar datos validados (se usan si no hay bloqueo duro)
        id_tipo = int(self.combo_tipo.get().split(" - ")[0]) if self.combo_tipo.get() else None
        self._oferta_validada = (
            codigo_producto, id_tipo, fecha_inicio_dt, fecha_fin_dt, descuento_val, stock_val
        )

        # --- Lógica combinada: regla + modelo ---
        if margen_bajo and modelo_riesgo:
            msg = (
                f"⛔ Ambas señales indican riesgo:\n"
                f"  • Margen estimado: {margen_texto} (mínimo: 5%)\n"
                f"  • 🤖 Modelo: {prob_no_rentable * 100:.0f}% probabilidad de no ser rentable\n"
                f"según el histórico de esta categoría\n\n"
                f"Marque la casilla para continuar a pesar del riesgo."
            )
            self.etiqueta_resultado.config(text=msg, bootstyle="danger")
            self._mostrar_advisory()
            self.boton_aprobar.config(state=DISABLED)

        elif margen_bajo:
            msg = (
                f"⚠ Margen estimado de {margen_texto} por debajo del mínimo (5%).\n"
                f"🤖 Modelo predictivo: sin alerta significativa."
            )
            self.etiqueta_resultado.config(text=msg, bootstyle="warning")
            self._ocultar_advisory()
            self.boton_aprobar.config(state="normal")

        elif modelo_riesgo:
            msg = (
                f"✔ Oferta válida según reglas de negocio (margen: {margen_texto}).\n"
                f"🤖 Predicción del modelo: {prob_no_rentable * 100:.0f}% de probabilidad "
                f"de no ser rentable según el histórico de esta categoría."
            )
            self.etiqueta_resultado.config(text=msg, bootstyle="warning")
            self._mostrar_advisory()
            self.boton_aprobar.config(state="normal")

        else:
            self.etiqueta_resultado.config(
                text="✔ Oferta válida. Sin traslapes ni riesgo de margen.",
                bootstyle="success"
            )
            self._ocultar_advisory()
            self.boton_aprobar.config(state="normal")

    def _registrar_oferta(self):
        """Registra la oferta respetando el orden de dependencias del esquema:
        1) Historial_Comercial  2) PROMOCION  3) Prod_Prom."""
        if not self._oferta_validada:
            return
        codigo_producto, id_tipo, fecha_inicio_dt, fecha_fin_dt, descuento_val, stock_val = self._oferta_validada

        conexion = obtener_conexion()
        cursor = conexion.cursor()
        try:
            # 1. Historial_Comercial: Id_promocion queda NULL hasta crear la PROMOCION
            cursor.execute("""
                INSERT INTO Historial_Comercial
                    (Id_promocion, Fecha_Registro, Cantidad_Productos_Vendidos, Cantidad_Ventas_Afectadas)
                VALUES (NULL, %s, 0, 0)
            """, (date.today(),))
            id_historial = cursor.lastrowid

            # 2. PROMOCION (Id_Tipo e Id_Historial son NOT NULL)
            cursor.execute("""
                INSERT INTO PROMOCION
                    (Id_Tipo, Id_Historial, Estado_Promocion, Fecha_Inicio, Porcentaje_Descuento, Fecha_Finalizacion)
                VALUES (%s, %s, 'Activa', %s, %s, %s)
            """, (id_tipo, id_historial, fecha_inicio_dt, descuento_val, fecha_fin_dt))
            id_promocion = cursor.lastrowid

            # 3. Cierra el ciclo de la FK en Historial_Comercial
            cursor.execute("""
                UPDATE Historial_Comercial SET Id_promocion = %s WHERE Id_Historial = %s
            """, (id_promocion, id_historial))

            # 4. Prod_Prom (Id_prom_pro es UNIQUE pero no AUTO_INCREMENT)
            cursor.execute("SELECT COALESCE(MAX(Id_prom_pro), 0) + 1 FROM Prod_Prom")
            siguiente_id_prom_pro = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO Prod_Prom
                    (Codigo_Producto, Codigo_Promocion, Id_prom_pro, Fecha_Asignacion, Porcentaje_Descuento, Stock_Afectado)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (codigo_producto, id_promocion, siguiente_id_prom_pro, date.today(), descuento_val, stock_val))

            conexion.commit()
            self.etiqueta_resultado.config(text="✔ Oferta registrada correctamente en Mineria_BD.")

            # Refresca el cronograma para que la nueva promo aparezca de inmediato
            self._construir_cronograma()
        except Exception as error:
            conexion.rollback()
            self.etiqueta_resultado.config(text=f"⚠ Error al registrar: {error}", bootstyle=DANGER)
        finally:
            cursor.close()
            conexion.close()
            self.boton_aprobar.config(state=DISABLED)
            self._oferta_validada = None
            self._ocultar_advisory()
            self.var_acepto_riesgo.set(False)


# ------------------------------------------------------------------
# EJECUCIÓN INDEPENDIENTE (solo para probar este panel de forma aislada)
# ------------------------------------------------------------------
# En la app final, este panel NO se ejecuta directamente: se instancia desde
# contenedor_principal.py cuando el usuario hace clic en "Gestión de Ofertas"
# en el Sidebar de Navegación (ver Figura de Arquitectura del Frontend).
# Este bloque solo sirve para verlo en pantalla mientras lo desarrollas.
if __name__ == "__main__":
    ventana = ttk.Window(title="Prueba - Panel de Simulación de Ofertas", themename="flatly")
    ventana.geometry("1400x800")
    ventana.minsize(1150, 650)
    PanelSimulacionOfertas(ventana)
    ventana.mainloop()