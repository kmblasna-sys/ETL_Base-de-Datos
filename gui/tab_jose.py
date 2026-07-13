import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from PIL import Image, ImageTk

# Asegurar acceso al directorio base
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from Conexion.conexion import obtener_conexion
from mysql.connector import Error

class MargenesPanel(tb.Frame):
    """
    3.6.4 Panel de Control de Precios y Auditoría Financiera (José)
    Integra la funcionalidad de validar la viabilidad financiera e identificar pérdidas 
    junto con la generación y visualización de la dispersión de márgenes.
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, padding=15, **kwargs)
        
        self.photo_img = None
        self.kpis = {}
        self.losses_list = []
        
        self.crear_layout()
        
        # Cargar los datos y el gráfico al inicializar
        self.actualizar_todo()

    def crear_layout(self):
        # --- ENCABEZADO ---
        header_frame = tb.Frame(self)
        header_frame.pack(fill=X, side=TOP, pady=(0, 15))
        
        tb.Label(
            header_frame, 
            text="💰 3.6.4 Control de Precios y Auditoría Financiera", 
            font=("Helvetica", 14, "bold"),
            bootstyle="success"
        ).pack(anchor=W)
        
        tb.Label(
            header_frame, 
            text="Responsable: José (Dashboard de Viabilidad e Impacto Promocional)", 
            font=("Helvetica", 10, "italic"),
            bootstyle="secondary"
        ).pack(anchor=W)

        # Barra de botones de acción
        actions_frame = tb.Frame(header_frame)
        actions_frame.pack(side=RIGHT, anchor=E, pady=(5, 0))
        
        self.btn_auditoria = tb.Button(
            actions_frame,
            text="🔄 Calcular Auditoría",
            bootstyle="success",
            padding=(10, 5),
            command=self.ejecutar_auditoria_background
        )
        self.btn_auditoria.pack(side=LEFT, padx=5)
        
        self.btn_grafico = tb.Button(
            actions_frame,
            text="📈 Actualizar Gráfico",
            bootstyle="info",
            padding=(10, 5),
            command=self.ejecutar_grafico_background
        )
        self.btn_grafico.pack(side=LEFT, padx=5)

        tb.Separator(self, bootstyle="secondary").pack(fill=X, pady=(0, 15))

        # --- CUERPO PRINCIPAL (Split Horizontal: Métricas/Tabla a la Izquierda y Gráfico a la Derecha) ---
        self.main_split = tb.Panedwindow(self, orient=HORIZONTAL)
        self.main_split.pack(fill=BOTH, expand=YES)
        
        # 1. PANEL IZQUIERDO: Métricas y Tabla
        left_panel = tb.Frame(self.main_split, padding=(0, 0, 10, 0))
        self.main_split.add(left_panel, weight=3)
        
        # Subpanel de Tarjetas de KPIs (Grid de 4 columnas)
        self.kpi_container = tb.Frame(left_panel)
        self.kpi_container.pack(fill=X, pady=(0, 15))
        self.inicializar_kpi_cards()
        
        # Subpanel de Resultados de Auditoría / Conclusión
        conclusion_card = tb.Labelframe(left_panel, text="📌 Conclusiones del Análisis", bootstyle="info", padding=12)
        conclusion_card.pack(fill=X, pady=(0, 15))
        
        self.lbl_conclusion = tb.Label(
            conclusion_card,
            text="Haz clic en 'Calcular Auditoría' para evaluar los datos actuales en Mineria_BD.",
            font=("Helvetica", 10),
            justify=LEFT,
            wraplength=550
        )
        self.lbl_conclusion.pack(fill=X, anchor=W)

        # Tabla de Detalles de Pérdidas
        table_label_frame = tb.Labelframe(left_panel, text="⚠️ Transacciones con Pérdida Detectadas", bootstyle="danger", padding=10)
        table_label_frame.pack(fill=BOTH, expand=YES)
        
        scroll_y = tb.Scrollbar(table_label_frame, orient=VERTICAL)
        scroll_x = tb.Scrollbar(table_label_frame, orient=HORIZONTAL)
        
        columnas = ("ID Detalle", "Código Prod.", "Cant. Vendida", "P. Venta Unit.", "Costo Unit.", "Dcto %", "P. Simulado", "Estado Margen")
        self.tree = tb.Treeview(
            table_label_frame, 
            columns=columnas, 
            show="headings", 
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
            bootstyle="danger"
        )
        
        scroll_y.config(command=self.tree.yview)
        scroll_x.config(command=self.tree.xview)
        
        # Configurar cabeceras de columnas
        anchors = {"ID Detalle": CENTER, "Código Prod.": W, "Cant. Vendida": CENTER, "P. Venta Unit.": E, "Costo Unit.": E, "Dcto %": CENTER, "P. Simulado": E, "Estado Margen": W}
        widths = {"ID Detalle": 70, "Código Prod.": 90, "Cant. Vendida": 90, "P. Venta Unit.": 90, "Costo Unit.": 90, "Dcto %": 60, "P. Simulado": 90, "Estado Margen": 120}
        
        for col in columnas:
            self.tree.heading(col, text=col, anchor=anchors[col])
            self.tree.column(col, width=widths[col], anchor=anchors[col], stretch=True)
            
        scroll_y.pack(side=RIGHT, fill=Y)
        scroll_x.pack(side=BOTTOM, fill=X)
        self.tree.pack(fill=BOTH, expand=YES)
        
        # 2. PANEL DERECHO: Visualización del Gráfico
        right_panel = tb.Labelframe(self.main_split, text="📊 Gráfico de Dispersión de Márgenes", bootstyle="info", padding=15)
        self.main_split.add(right_panel, weight=2)
        
        self.lbl_imagen = tb.Label(
            right_panel, 
            text="Gráfico no cargado", 
            font=("Helvetica", 10, "italic"),
            anchor=CENTER,
            justify=CENTER
        )
        self.lbl_imagen.pack(fill=BOTH, expand=YES)

    def inicializar_kpi_cards(self):
        # Crear los labels de métricas iniciales
        self.cards = {}
        metricas = [
            ("total", "Transacciones", "0", "secondary"),
            ("perdidas", "Pérdidas Netas", "0 (0.0%)", "danger"),
            ("salvadas", "Simulación Salvadas", "0 (0.0%)", "success"),
            ("insalvables", "Insalvables", "0 (0.0%)", "warning")
        ]
        
        for i, (key, title, val, style) in enumerate(metricas):
            self.kpi_container.columnconfigure(i, weight=1, uniform="metricas")
            
            card = tb.Frame(self.kpi_container, bootstyle="light", padding=10)
            card.grid(row=0, column=i, padx=5, sticky="nsew")
            
            lbl_title = tb.Label(card, text=title, font=("Helvetica", 9, "bold"), bootstyle=style)
            lbl_title.pack(anchor=W)
            
            lbl_val = tb.Label(card, text=val, font=("Helvetica", 13, "bold"))
            lbl_val.pack(anchor=W, pady=(5, 0))
            
            self.cards[key] = lbl_val

    def actualizar_todo(self):
        self.ejecutar_auditoria_background()
        self.cargar_imagen_grafico()

    def cargar_imagen_grafico(self):
        ruta_img = os.path.join(BASE_DIR, "dispersion_margenes.png")
        if os.path.exists(ruta_img):
            try:
                # Cargar y redimensionar con PIL
                img = Image.open(ruta_img)
                # Escalado proporcional para adaptarse
                img = img.resize((480, 310), Image.Resampling.LANCZOS)
                self.photo_img = ImageTk.PhotoImage(img)
                self.lbl_imagen.config(image=self.photo_img, text="")
            except Exception as e:
                self.lbl_imagen.config(text=f"Error al renderizar gráfico:\n{e}", image='')
        else:
            self.lbl_imagen.config(text="El archivo de gráfico de dispersión no existe.\nPresiona 'Actualizar Gráfico' para generarlo.", image='')

    def ejecutar_grafico_background(self):
        self.btn_grafico.config(state="disabled")
        self.lbl_imagen.config(image='', text="Generando gráfico de dispersión...\nPor favor espera.")
        
        def worker():
            try:
                # Importación dinámica del script existente
                from validaciones_y_graficas.graficar_dispersion import graficar_dispersion_margenes
                graficar_dispersion_margenes()
                self.after(100, self.finalizar_grafico_exito)
            except Exception as e:
                self.after(100, lambda: messagebox.showerror("Error", f"Error al generar gráfico: {e}"))
                self.after(100, self.finalizar_grafico_error)
                
        threading.Thread(target=worker, daemon=True).start()

    def finalizar_grafico_exito(self):
        self.btn_grafico.config(state="normal")
        self.cargar_imagen_grafico()
        
    def finalizar_grafico_error(self):
        self.btn_grafico.config(state="normal")
        self.lbl_imagen.config(text="Error al generar el gráfico.")

    def ejecutar_auditoria_background(self):
        self.btn_auditoria.config(state="disabled")
        self.lbl_conclusion.config(text="Analizando base de datos local...")
        
        def worker():
            conexion = obtener_conexion()
            if not conexion:
                self.after(100, lambda: self.finalizar_auditoria_error("No se pudo conectar a la base de datos local."))
                return

            cursor = None
            try:
                cursor = conexion.cursor()
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
                    self.after(100, lambda: self.finalizar_auditoria_error("Base de datos vacía. Carga los datos primero."))
                    return

                transacciones_con_perdida = 0
                transacciones_salvadas = 0
                transacciones_insalvables = 0
                losses_list = []

                for row in rows:
                    id_trans, cod_prod, cant_vendida, venta_total, compra_total, compra_qty, dcto_prom = row
                    
                    cant_vendida = int(cant_vendida or 0)
                    compra_qty = int(compra_qty or 1)
                    venta_total = float(venta_total or 0.0)
                    compra_total = float(compra_total or 0.0)
                    dcto_prom = float(dcto_prom or 0.0)

                    if cant_vendida <= 0 or compra_qty <= 0:
                        continue

                    precio_venta_unitario_con_dcto = venta_total / cant_vendida
                    costo_compra_unitario = compra_total / compra_qty

                    # Identificar pérdidas
                    if precio_venta_unitario_con_dcto <= costo_compra_unitario:
                        transacciones_con_perdida += 1
                        
                        # Simular Restricción Dinámica de Descuentos
                        factor_descuento = dcto_prom / 100.0
                        if factor_descuento < 1.0:
                            precio_venta_unitario_sin_dcto = precio_venta_unitario_con_dcto / (1.0 - factor_descuento)
                        else:
                            precio_venta_unitario_sin_dcto = precio_venta_unitario_con_dcto

                        if precio_venta_unitario_sin_dcto > 0:
                            margen_base = (precio_venta_unitario_sin_dcto - costo_compra_unitario) / precio_venta_unitario_sin_dcto
                        else:
                            margen_base = 0.0

                        descuento_maximo_permitido = margen_base - 0.05
                        if descuento_maximo_permitido < 0.0:
                            descuento_maximo_permitido = 0.0

                        descuento_simulado = min(factor_descuento, descuento_maximo_permitido)
                        precio_venta_simulado = precio_venta_unitario_sin_dcto * (1.0 - descuento_simulado)
                        
                        margen_minimo_objetivo = costo_compra_unitario * 1.05
                        if precio_venta_simulado >= margen_minimo_objetivo:
                            transacciones_salvadas += 1
                            estado = "Salvada (>=5%)"
                        else:
                            transacciones_insalvables += 1
                            estado = "Insalvable (<5%)"

                        losses_list.append((
                            id_trans,
                            cod_prod,
                            cant_vendida,
                            f"${precio_venta_unitario_con_dcto:.2f}",
                            f"${costo_compra_unitario:.2f}",
                            f"{dcto_prom:.1f}%",
                            f"${precio_venta_simulado:.2f}",
                            estado
                        ))

                # Preparar métricas
                pct_perdidas = (transacciones_con_perdida / total_transacciones) * 100
                if transacciones_con_perdida > 0:
                    pct_salvadas = (transacciones_salvadas / transacciones_con_perdida) * 100
                    pct_insalvables = (transacciones_insalvables / transacciones_con_perdida) * 100
                else:
                    pct_salvadas = 0.0
                    pct_insalvables = 0.0

                kpis = {
                    "total": f"{total_transacciones}",
                    "perdidas": f"{transacciones_con_perdida} ({pct_perdidas:.2f}%)",
                    "salvadas": f"{transacciones_salvadas} ({pct_salvadas:.2f}%)",
                    "insalvables": f"{transacciones_insalvables} ({pct_insalvables:.2f}%)"
                }

                # Conclusión textual
                conclusion = (
                    f"Se analizaron {total_transacciones} transacciones en total.\n"
                    f"⚠️ El {pct_perdidas:.2f}% ({transacciones_con_perdida} ventas) registraron pérdidas netas reales.\n"
                    f"🛡️ La simulación de Restricción Dinámica de Descuentos rescató a {transacciones_salvadas} transacciones "
                    f"({pct_salvadas:.2f}% de las pérdidas), asegurando ganancias.\n"
                    f"📌 {transacciones_insalvables} transacciones son insalvables con solo limitar descuentos, "
                    f"debido a que su precio base no cubre un 5% de margen sobre el costo de adquisición."
                )

                self.after(100, lambda: self.finalizar_auditoria_exito(kpis, losses_list, conclusion))

            except Error as e:
                self.after(100, lambda: self.finalizar_auditoria_error(f"Error SQL: {e}"))
            except Exception as ex:
                self.after(100, lambda: self.finalizar_auditoria_error(f"Error inesperado: {ex}"))
            finally:
                if cursor:
                    cursor.close()
                if conexion and conexion.is_connected():
                    conexion.close()
                    
        threading.Thread(target=worker, daemon=True).start()

    def finalizar_auditoria_exito(self, kpis, losses, conclusion):
        self.btn_auditoria.config(state="normal")
        self.lbl_conclusion.config(text=conclusion)
        self.losses_list = losses
        
        # Actualizar tarjetas de KPI
        for key, val in kpis.items():
            if key in self.cards:
                self.cards[key].config(text=val)
                
        # Limpiar y rellenar tabla
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        for row in losses:
            self.tree.insert("", END, values=row)

    def finalizar_auditoria_error(self, mensaje):
        self.btn_auditoria.config(state="normal")
        self.lbl_conclusion.config(text=f"⚠️ ERROR: {mensaje}")
        # Limpiar KPI cards
        for key in self.cards:
            self.cards[key].config(text="--")
        # Limpiar tabla
        for item in self.tree.get_children():
            self.tree.delete(item)
