"""
Panel de Simulación y Control de Ofertas Vigentes
--------------------------------------------------
Módulo: panel_simulacion_ofertas.py
Proyecto: Auditoría y Simulación Promocional - Walmart (Mineria_BD)

Componentes:
1. Cronograma visual (Gantt) de las campañas activas: cada promoción se
   representa como una barra horizontal cuya longitud indica la duración;
   barras en rojo señalan traslape de fechas (detección global, no solo
   dentro del filtro). Fechas de inicio y fin aparecen al costado de
   cada barra. Filtro por periodos de 6 meses (Jul–Jun).
2. Simulador de ofertas: antes de registrar una nueva promoción, cruza el
   rango propuesto contra Prod_Prom/PROMOCION para detectar traslapes y
   estima si el margen resultante caería bajo el 5% mínimo.
"""

import sys
import os
import calendar
import tkinter as tk
from datetime import date, datetime, timedelta
from collections import OrderedDict

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
import matplotlib.dates as mdates
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
# La carpeta gui queda en el path para importar el selector reutilizable.
_gui_dir = os.path.dirname(os.path.abspath(__file__))
if _gui_dir not in sys.path:
    sys.path.append(_gui_dir)

from Conexion.conexion import obtener_conexion
from busqueda_producto import SelectorProductoPorNombre


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
        """Controles fijos del cronograma: selector de año y panel de productos."""
        frame_controles = ttk.Frame(self.frame_cronograma)
        frame_controles.pack(fill=X, pady=(0, 8))

        ttk.Label(frame_controles, text="Periodo:").pack(side=LEFT, padx=(0, 5))
        periodos = self._obtener_anios_disponibles()
        self.combo_anio = ttk.Combobox(
            frame_controles,             values=["General"] + periodos,
            state="readonly", width=20
        )
        self.combo_anio.pack(side=LEFT)
        self.combo_anio.current(0)
        self.combo_anio.bind("<<ComboboxSelected>>", lambda e: self._construir_cronograma())

        # Panel de productos por promoción (parte inferior)
        self.frame_productos = ttk.Labelframe(
            self.frame_cronograma, text="Productos por Promoción", padding=5
        )
        self.frame_productos.pack(side=BOTTOM, fill=X, padx=0, pady=(8, 0))

        columnas = ("promo", "codigo", "nombre", "categoria", "dcto", "precio_dcto")
        self.tree_productos = ttk.Treeview(
            self.frame_productos, columns=columnas, show="headings",
            height=6, bootstyle="info"
        )
        self.tree_productos.heading("promo", text="Promo")
        self.tree_productos.heading("codigo", text="Código")
        self.tree_productos.heading("nombre", text="Nombre")
        self.tree_productos.heading("categoria", text="Categoría")
        self.tree_productos.heading("dcto", text="Dcto.%")
        self.tree_productos.heading("precio_dcto", text="Precio c/Dcto.")

        self.tree_productos.column("promo", width=45, anchor=CENTER)
        self.tree_productos.column("codigo", width=80)
        self.tree_productos.column("nombre", width=120)
        self.tree_productos.column("categoria", width=85)
        self.tree_productos.column("dcto", width=45, anchor=CENTER)
        self.tree_productos.column("precio_dcto", width=80, anchor=E)

        scroll = ttk.Scrollbar(
            self.frame_productos, orient=VERTICAL,
            command=self.tree_productos.yview
        )
        self.tree_productos.configure(yscrollcommand=scroll.set)
        self.tree_productos.pack(side=LEFT, fill=BOTH, expand=True)
        scroll.pack(side=RIGHT, fill=Y)

        # Gráfico Gantt (toma el espacio restante arriba)
        self.frame_grafico = ttk.Frame(self.frame_cronograma)
        self.frame_grafico.pack(fill=BOTH, expand=True)

    def _obtener_anios_disponibles(self):
        """Retorna los periodos de 6 meses disponibles como strings."""
        conexion = obtener_conexion()
        if conexion is None:
            return []
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT DISTINCT YEAR(Fecha_Inicio) AS anio
            FROM PROMOCION
            WHERE Estado_Promocion = 'Activa'
              AND Fecha_Finalizacion >= Fecha_Inicio
            ORDER BY anio
        """)
        anios = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conexion.close()

        MES_ABREV = {
            7: "Jul", 1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr",
            5: "May", 6: "Jun", 8: "Ago", 9: "Sep", 10: "Oct",
            11: "Nov", 12: "Dic"
        }
        periodos = []
        if anios:
            anio_min = min(anios)
            anio_max = max(anios)
            # Periodos de Jul a Jun: Jul 2019–Jun 2020, Jul 2020–Jun 2021, ...
            for anio in range(anio_max, anio_min - 1, -1):
                label = f"Jul {anio} – Jun {anio + 1}"
                periodos.append(label)
        return periodos

    def _obtener_promociones_activas(self, fecha_inicio=None, fecha_fin=None):
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
        params = []
        if fecha_inicio is not None:
            query += " AND Fecha_Finalizacion >= %s"
            params.append(fecha_inicio)
        if fecha_fin is not None:
            query += " AND Fecha_Inicio <= %s"
            params.append(fecha_fin)
        query += " ORDER BY Fecha_Inicio"
        cursor.execute(query, params)
        datos = cursor.fetchall()
        cursor.close()
        conexion.close()
        return datos

    def _obtener_todas_las_promociones(self):
        """Retorna todas las promociones activas sin filtro de fecha."""
        return self._obtener_promociones_activas()

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
        sel = self.combo_anio.get()

        # --- Parsear periodo seleccionado ---
        es_todas = (sel == "General")
        fecha_inicio_filtro = None
        fecha_fin_filtro = None
        if not es_todas:
            # Formato: "Jul 2019 – Jun 2020"
            partes = sel.replace("–", "-").split("-")
            partes_inicio = partes[0].strip().split()
            partes_fin = partes[1].strip().split()
            MES_NUM = {"Ene": 1, "Feb": 2, "Mar": 3, "Abr": 4, "May": 5, "Jun": 6,
                       "Jul": 7, "Ago": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dic": 12}
            mes_ini = MES_NUM[partes_inicio[0]]
            anio_ini = int(partes_inicio[1])
            mes_fin = MES_NUM[partes_fin[0]]
            anio_fin = int(partes_fin[1])
            fecha_inicio_filtro = date(anio_ini, mes_ini, 1)
            if mes_fin == 12:
                fecha_fin_filtro = date(anio_fin, 12, 31)
            else:
                fecha_fin_filtro = date(anio_fin, mes_fin + 1, 1) - timedelta(days=1)

        # --- Obtener promociones filtradas y TODAS (para traslapes globales) ---
        promociones = self._obtener_promociones_activas(
            fecha_inicio=fecha_inicio_filtro, fecha_fin=fecha_fin_filtro
        )
        todas_promociones = self._obtener_todas_las_promociones()
        conflictivas = self._detectar_traslapes(todas_promociones)

        for widget in self.frame_grafico.winfo_children():
            widget.destroy()

        if not promociones:
            if not es_todas:
                mensaje = f"No hay promociones activas en el periodo {sel}."
            else:
                mensaje = "No hay promociones activas en el dataset."
            ttk.Label(
                self.frame_grafico, text=mensaje, justify=CENTER, bootstyle="secondary"
            ).pack(expand=True)
            self._cargar_productos_promociones([])
            return

        # --- Rango del eje X ---
        if es_todas:
            fecha_min = date(2019, 11, 1)
            fecha_max = date(2023, 12, 31)
        else:
            fecha_min = fecha_inicio_filtro
            fecha_max = fecha_fin_filtro
        margen = timedelta(days=15)

        n_promos = len(promociones)
        altura = max(3, 0.5 + n_promos * 0.42)

        figura = Figure(figsize=(8, altura), dpi=100)
        ax = figura.add_subplot(111)
        ax.margins(y=0.08)

        for idx, (id_promo, inicio, fin) in enumerate(promociones):
            duracion = (fin - inicio).days
            if duracion <= 0:
                duracion = 1
            color = "#E53935" if id_promo in conflictivas else "#0071CE"
            ax.barh(idx, duracion, left=inicio, height=0.4,
                    color=color, edgecolor="white", zorder=2)

            # --- Promo ID a la izquierda de la barra ---
            ax.text(inicio - timedelta(days=3), idx, f"Promo {id_promo}",
                    va="center", ha="right", fontsize=6.5,
                    fontweight="bold", color="#333333", clip_on=True)

            # --- Fechas a la derecha FUERA de la barra ---
            texto_fechas = f"{inicio.strftime('%d/%m/%Y')} – {fin.strftime('%d/%m/%Y')}"
            ax.text(fin + timedelta(days=4), idx, texto_fechas,
                    va="center", ha="left", fontsize=6, color="#555555",
                    clip_on=True)

        # --- Eje X: meses como columnas de referencia ---
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%Y'))
        ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonthday=15))

        ax.set_xlim(fecha_min - margen, fecha_max + margen)
        ax.grid(axis="x", which="major", linestyle="--", alpha=0.35, color="#B0BEC5")
        ax.grid(axis="x", which="minor", linestyle=":", alpha=0.15, color="#CFD8DC")

        # --- Meses arriba ---
        ax.xaxis.set_ticks_position("both")
        ax.tick_params(axis="x", which="major", labelsize=6, length=4)
        ax.xaxis.set_label_position("top")

        # --- Eje Y ---
        ax.set_ylim(-0.5, n_promos - 0.5)
        ax.set_yticks([])
        ax.set_xlabel("Línea de Tiempo (meses)", fontsize=8, labelpad=8)
        ax.set_ylabel("")

        ax.set_title(f"Cronograma de Campañas  {sel}",
                     fontsize=9, fontweight="bold", pad=12)

        ax.spines["top"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["right"].set_visible(False)

        # --- Leyenda ---
        from matplotlib.patches import Patch
        elementos_leyenda = [
            Patch(facecolor="#0071CE", edgecolor="white", label="Sin traslape"),
            Patch(facecolor="#E53935", edgecolor="white", label="Con traslape"),
        ]
        ax.legend(handles=elementos_leyenda, loc="lower right",
                  fontsize=6, framealpha=0.9, edgecolor="#CFD8DC")

        figura.tight_layout()

        lienzo = FigureCanvasTkAgg(figura, master=self.frame_grafico)
        lienzo.draw()
        lienzo.get_tk_widget().pack(fill=BOTH, expand=True)

        self._cargar_productos_promociones(
            [id_p for id_p, _, _ in promociones]
        )

    def _cargar_productos_promociones(self, ids_promociones):
        """Carga y muestra en el Treeview los productos de las promociones dadas.
        Para promociones con ≤5 productos muestra cada uno; para las demás
        muestra un resumen de categorías."""
        for item in self.tree_productos.get_children():
            self.tree_productos.delete(item)

        if not ids_promociones:
            return

        conexion = obtener_conexion()
        if conexion is None:
            return
        cursor = conexion.cursor()
        try:
            placeholders = ",".join(["%s"] * len(ids_promociones))
            cursor.execute(f"""
                SELECT
                    pp.Codigo_Promocion,
                    pr.Codigo_de_Producto,
                    pr.Nombre,
                    cat.nombre_categoria,
                    pp.Porcentaje_Descuento,
                    (
                        SELECT v.Precio_venta
                        FROM DetalleVenta dv2
                        JOIN Venta v ON dv2.Numero_Transaccion = v.Numero_Transaccion
                        WHERE dv2.Codigo_de_Producto = pr.Codigo_de_Producto
                        ORDER BY v.Fecha_Hora_Emision DESC
                        LIMIT 1
                    ) AS Precio_Base
                FROM Prod_Prom pp
                JOIN Producto pr ON pp.Codigo_Producto = pr.Codigo_de_Producto
                LEFT JOIN Categoria cat ON pr.id_categoria = cat.id_categoria
                WHERE pp.Codigo_Promocion IN ({placeholders})
                ORDER BY pp.Codigo_Promocion, pr.Nombre
            """, ids_promociones)
            filas = cursor.fetchall()
        except Exception:
            filas = []
        finally:
            cursor.close()
            conexion.close()

        # Agrupar por promoción
        por_promo = OrderedDict()
        for promo_id, cod, nombre, cat, dcto, precio_base in filas:
            if promo_id not in por_promo:
                por_promo[promo_id] = []
            por_promo[promo_id].append((cod, nombre, cat, dcto, precio_base))

        for promo_id, productos in por_promo.items():
            dcto_val = float(productos[0][3] or 0)
            if len(productos) <= 5:
                for cod, nombre, cat, dcto, precio_base in productos:
                    pb = float(precio_base) if precio_base else 0.0
                    d = float(dcto or 0)
                    precio_dcto = pb * (1 - d / 100) if pb > 0 else 0.0
                    self.tree_productos.insert("", "end", values=(
                        promo_id,
                        cod or "",
                        (nombre or "").split(",")[0].strip(),
                        cat or "",
                        f"{d:.0f}%" if d > 0 else "-",
                        f"${precio_dcto:.2f}" if precio_dcto > 0 else "-"
                    ))
            else:
                categorias = list(set(p[2] for p in productos if p[2]))
                cat_texto = ", ".join(categorias[:3])
                if len(categorias) > 3:
                    cat_texto += f" (+{len(categorias) - 3})"
                self.tree_productos.insert("", "end", values=(
                    promo_id,
                    f"{len(productos)} productos",
                    "",
                    cat_texto,
                    f"{dcto_val:.0f}%",
                    "-"
                ))

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

    def _cargar_productos_selector(self):
        """Carga el catálogo de productos para el selector con búsqueda."""
        conexion = obtener_conexion()
        if conexion is None:
            self.selector_producto.set_productos([])
            return
        cursor = conexion.cursor()
        try:
            cursor.execute(
                "SELECT Codigo_de_Producto, Nombre FROM Producto ORDER BY Nombre"
            )
            self.selector_producto.set_productos(cursor.fetchall())
        except Exception:
            self.selector_producto.set_productos([])
        finally:
            cursor.close()
            conexion.close()

    def _meses_opciones(self):
        return [
            (1, "Ene"), (2, "Feb"), (3, "Mar"), (4, "Abr"),
            (5, "May"), (6, "Jun"), (7, "Jul"), (8, "Ago"),
            (9, "Sep"), (10, "Oct"), (11, "Nov"), (12, "Dic"),
        ]

    def _anios_sugeridos(self):
        """Año actual y el siguiente."""
        anio = date.today().year
        return [anio, anio + 1]

    def _crear_selector_fecha(self, padre, fecha_inicial=None):
        """Crea combos independientes Año / Mes / Día y retorna un dict de widgets."""
        if fecha_inicial is None:
            fecha_inicial = date.today()

        frame = ttk.Frame(padre)
        frame.pack(fill=X)

        anios = self._anios_sugeridos()
        meses = self._meses_opciones()
        labels_mes = [f"{num:02d} - {abrev}" for num, abrev in meses]

        ttk.Label(frame, text="Año").pack(side=LEFT)
        combo_anio = ttk.Combobox(
            frame, values=anios, state="readonly", width=6
        )
        combo_anio.pack(side=LEFT, padx=(2, 6))
        if fecha_inicial.year in anios:
            combo_anio.set(fecha_inicial.year)
        else:
            combo_anio.current(0)

        ttk.Label(frame, text="Mes").pack(side=LEFT)
        combo_mes = ttk.Combobox(
            frame, values=labels_mes, state="readonly", width=9
        )
        combo_mes.pack(side=LEFT, padx=(2, 6))
        combo_mes.current(fecha_inicial.month - 1)

        ttk.Label(frame, text="Día").pack(side=LEFT)
        combo_dia = ttk.Combobox(frame, state="readonly", width=4)
        combo_dia.pack(side=LEFT, padx=(2, 0))

        selector = {
            "anio": combo_anio,
            "mes": combo_mes,
            "dia": combo_dia,
        }

        def _actualizar_dias(_event=None):
            try:
                anio = int(combo_anio.get())
                mes = int(combo_mes.get().split(" - ")[0])
            except (ValueError, IndexError):
                return
            max_dia = calendar.monthrange(anio, mes)[1]
            dias = list(range(1, max_dia + 1))
            dia_actual = combo_dia.get()
            combo_dia.configure(values=dias)
            if dia_actual and dia_actual.isdigit() and int(dia_actual) in dias:
                combo_dia.set(int(dia_actual))
            else:
                dia_pref = min(fecha_inicial.day, max_dia)
                combo_dia.set(dia_pref)

        combo_anio.bind("<<ComboboxSelected>>", _actualizar_dias)
        combo_mes.bind("<<ComboboxSelected>>", _actualizar_dias)
        _actualizar_dias()
        return selector

    def _fecha_desde_selector(self, selector):
        """Arma un date a partir de los combos Año/Mes/Día. None si falta algo."""
        try:
            anio = int(selector["anio"].get())
            mes = int(selector["mes"].get().split(" - ")[0])
            dia = int(selector["dia"].get())
            return date(anio, mes, dia)
        except (ValueError, TypeError, IndexError, KeyError):
            return None

    def _construir_formulario_simulador(self):
        self._tipos_promocion = self._obtener_tipos_promocion()
        opciones_tipo = [f"{tid} - {nombre}" for tid, nombre in self._tipos_promocion]

        producto_box = ttk.Labelframe(
            self.frame_simulador, text="Producto", padding=8
        )
        producto_box.pack(fill=X, pady=(5, 0))
        self.selector_producto = SelectorProductoPorNombre(
            producto_box, altura_lista=5
        )
        self.selector_producto.pack(fill=X)
        self._cargar_productos_selector()

        ttk.Label(self.frame_simulador, text="Tipo de Promoción:").pack(anchor=W, pady=(10, 0))
        self.combo_tipo = ttk.Combobox(self.frame_simulador, values=opciones_tipo, state="readonly")
        self.combo_tipo.pack(fill=X)
        if opciones_tipo:
            self.combo_tipo.current(0)

        hoy = date.today()
        ttk.Label(self.frame_simulador, text="Fecha Inicio:").pack(anchor=W, pady=(10, 0))
        self.selector_fecha_inicio = self._crear_selector_fecha(
            self.frame_simulador, fecha_inicial=hoy
        )

        ttk.Label(self.frame_simulador, text="Fecha Fin:").pack(anchor=W, pady=(10, 0))
        self.selector_fecha_fin = self._crear_selector_fecha(
            self.frame_simulador, fecha_inicial=hoy + timedelta(days=7)
        )

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
        codigo_producto = self.selector_producto.get_codigo()
        fecha_inicio_dt = self._fecha_desde_selector(self.selector_fecha_inicio)
        fecha_fin_dt = self._fecha_desde_selector(self.selector_fecha_fin)
        descuento_raw = self.entrada_descuento.get().strip().replace("%", "")
        stock_raw = self.entrada_stock.get().strip()

        if not codigo_producto:
            self.etiqueta_resultado.config(
                text="⚠️ Busca y selecciona un producto de la lista.", bootstyle="danger"
            )
            self.boton_aprobar.config(state=DISABLED)
            self._oferta_validada = None
            return

        if not all([fecha_inicio_dt, fecha_fin_dt, descuento_raw, stock_raw]):
            self.etiqueta_resultado.config(
                text="⚠️ Todos los campos son obligatorios.", bootstyle="danger"
            )
            self.boton_aprobar.config(state=DISABLED)
            self._oferta_validada = None
            return

        # 2. Validación de formato (descuento, stock, fechas)
        descuento_val = None
        stock_val = None

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

        if fecha_fin_dt < fecha_inicio_dt:
            errores.append("- La fecha de fin no puede ser anterior a la de inicio.")

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
            self.selector_producto.limpiar()

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