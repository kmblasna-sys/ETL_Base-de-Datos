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
    Dashboard integrado que aplica Minería de Datos (Árbol de Decisión) para
    descubrir reglas de riesgo comercial y proyectar retornos financieros de auditoría.
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, padding=15, **kwargs)
        
        self.photo_img = None
        self.cards = {}
        self.losses_list = []
        self.model = None
        
        self.crear_layout()
        self.actualizar_todo()

    def crear_layout(self):
        # ==========================================
        # 1. ENCABEZADO Y ACCIONES
        # ==========================================
        header_frame = tb.Frame(self)
        header_frame.pack(fill=X, side=TOP, pady=(0, 10))
        
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

        # Botones de Acción
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

        tb.Separator(self, bootstyle="secondary").pack(fill=X, pady=(0, 10))

        # ==========================================
        # 2. FILA DE METRICAS (KPI CARDS)
        # ==========================================
        self.kpi_container = tb.Frame(self)
        self.kpi_container.pack(fill=X, pady=(0, 10))
        self.inicializar_kpi_cards()

        # ==========================================
        # 3. SECCIÓN MEDIA: TABLA DE ALERTAS Y GRÁFICO (Panedwindow)
        # ==========================================
        self.middle_split = tb.Panedwindow(self, orient=HORIZONTAL)
        self.middle_split.pack(fill=BOTH, expand=YES, pady=(0, 10))
        
        # Panel Izquierdo: Tabla
        table_label_frame = tb.Labelframe(self.middle_split, text="⚠️ Ventas con Pérdida Crítica Detectadas", bootstyle="danger", padding=10)
        self.middle_split.add(table_label_frame, weight=3)
        
        self.lbl_table_summary = tb.Label(
            table_label_frame,
            text="Calcula la auditoría para visualizar las alertas financieras.",
            font=("Helvetica", 9, "bold"),
            bootstyle="danger"
        )
        self.lbl_table_summary.pack(fill=X, pady=(0, 5), anchor=W)
        
        # Treeview Scrollbar
        scroll_y = tb.Scrollbar(table_label_frame, orient=VERTICAL)
        scroll_x = tb.Scrollbar(table_label_frame, orient=HORIZONTAL)
        
        columnas = ("ID Detalle", "Código Prod.", "Cant. Vendida", "P. Final Unit.", "Costo Unit.", "Dcto %", "Pérdida Unit.", "P. Simulado", "Recomendación")
        self.tree = tb.Treeview(
            table_label_frame, 
            columns=columnas, 
            show="headings", 
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
            height=8,
            bootstyle="danger"
        )
        
        scroll_y.config(command=self.tree.yview)
        scroll_x.config(command=self.tree.xview)
        
        anchors = {
            "ID Detalle": CENTER, "Código Prod.": W, "Cant. Vendida": CENTER, 
            "P. Final Unit.": E, "Costo Unit.": E, "Dcto %": CENTER, 
            "Pérdida Unit.": E, "P. Simulado": E, "Recomendación": CENTER
        }
        widths = {
            "ID Detalle": 65, "Código Prod.": 80, "Cant. Vendida": 75, 
            "P. Final Unit.": 80, "Costo Unit.": 80, "Dcto %": 55, 
            "Pérdida Unit.": 80, "P. Simulado": 80, "Recomendación": 95
        }
        
        for col in columnas:
            self.tree.heading(col, text=col, anchor=anchors[col])
            self.tree.column(col, width=widths[col], anchor=anchors[col], stretch=True)
            
        scroll_y.pack(side=RIGHT, fill=Y)
        scroll_x.pack(side=BOTTOM, fill=X)
        self.tree.pack(fill=BOTH, expand=YES)
        
        # Panel Derecho: Gráfico
        right_panel = tb.Labelframe(self.middle_split, text="📊 Gráfico de Dispersión de Márgenes", bootstyle="info", padding=10)
        self.middle_split.add(right_panel, weight=2)
        
        self.lbl_imagen = tb.Label(
            right_panel, 
            text="Gráfico no cargado", 
            font=("Helvetica", 10, "italic"),
            anchor=CENTER,
            justify=CENTER
        )
        self.lbl_imagen.pack(fill=BOTH, expand=YES)

        # ==========================================
        # 4. SECCIÓN INFERIOR: CONCLUSIONES (IZQ) Y INTELIGENCIA PROYECTADA ML (DER)
        # ==========================================
        self.bottom_frame = tb.Frame(self)
        self.bottom_frame.pack(fill=X, side=BOTTOM)
        
        # Columna Izquierda: Conclusiones
        left_bottom_frame = tb.Labelframe(self.bottom_frame, text="📊 Conclusiones de Negocio de la Auditoría", bootstyle="success", padding=12)
        left_bottom_frame.pack(side=LEFT, fill=BOTH, expand=YES, padx=(0, 8))
        
        self.lbl_conclusion = tb.Label(
            left_bottom_frame,
            text="Calculando auditoría comercial...",
            font=("Helvetica", 10),
            justify=LEFT,
            wraplength=420
        )
        self.lbl_conclusion.pack(fill=X, anchor=W, pady=(0, 8))
        
        tb.Separator(left_bottom_frame, bootstyle="secondary").pack(fill=X, pady=5)
        
        self.lbl_accuracy = tb.Label(
            left_bottom_frame, 
            text="Precisión del Modelo (Accuracy): --", 
            font=("Helvetica", 10, "bold"),
            bootstyle="success"
        )
        self.lbl_accuracy.pack(anchor=W, pady=2)
        
        self.lbl_importances = tb.Label(
            left_bottom_frame, 
            text="Importancia de Atributos:\n (Ejecuta la auditoría para calcularlas)", 
            font=("Helvetica", 9),
            justify=LEFT
        )
        self.lbl_importances.pack(anchor=W, pady=2)

        # Columna Derecha: Proyecciones Numéricas y Reglas de Minería de Datos
        right_bottom_frame = tb.Labelframe(self.bottom_frame, text="🔮 Proyecciones Financieras y Reglas ML (Minería)", bootstyle="info", padding=12)
        right_bottom_frame.pack(side=LEFT, fill=BOTH, expand=YES, padx=(8, 0))
        
        # Grid para Proyecciones Financieras
        grid_frame = tb.Frame(right_bottom_frame)
        grid_frame.pack(side=TOP, fill=X, pady=(0, 8))
        
        tb.Label(grid_frame, text="Pérdida Crítica Acumulada:", font=("Helvetica", 9)).grid(row=0, column=0, sticky=W, pady=2)
        self.lbl_loss_total = tb.Label(grid_frame, text="--", font=("Helvetica", 9, "bold"), bootstyle="danger")
        self.lbl_loss_total.grid(row=0, column=1, sticky=W, padx=10, pady=2)
        
        tb.Label(grid_frame, text="Recuperación por Descuento:", font=("Helvetica", 9)).grid(row=1, column=0, sticky=W, pady=2)
        self.lbl_rec_dcto = tb.Label(grid_frame, text="--", font=("Helvetica", 9, "bold"), bootstyle="success")
        self.lbl_rec_dcto.grid(row=1, column=1, sticky=W, padx=10, pady=2)
        
        tb.Label(grid_frame, text="Recuperación por Catálogo:", font=("Helvetica", 9)).grid(row=2, column=0, sticky=W, pady=2)
        self.lbl_rec_base = tb.Label(grid_frame, text="--", font=("Helvetica", 9, "bold"), bootstyle="success")
        self.lbl_rec_base.grid(row=2, column=1, sticky=W, padx=10, pady=2)
        
        tb.Label(grid_frame, text="Retorno Neto Proyectado:", font=("Helvetica", 9, "bold")).grid(row=3, column=0, sticky=W, pady=2)
        self.lbl_rec_total = tb.Label(grid_frame, text="--", font=("Helvetica", 10, "bold"), bootstyle="success")
        self.lbl_rec_total.grid(row=3, column=1, sticky=W, padx=10, pady=2)
        
        tb.Separator(right_bottom_frame, bootstyle="secondary").pack(fill=X, pady=4)
        
        # Caja de Reglas ML
        self.lbl_reglas = tb.Label(
            right_bottom_frame,
            text="Reglas de Riesgo Extraídas por el Algoritmo:\n (Ejecuta la auditoría para calcularlas)",
            font=("Helvetica", 9, "italic"),
            justify=LEFT,
            wraplength=380
        )
        self.lbl_reglas.pack(fill=X, anchor=W, pady=2)

    def inicializar_kpi_cards(self):
        self.cards = {}
        metricas = [
            ("total", "Transacciones", "0", "secondary"),
            ("perdidas", "Pérdidas Críticas (> $500)", "0 (0.0%)", "danger"),
            ("salvadas", "Ajustar Dcto.", "0 (0.0%)", "success"),
            ("insalvables", "Ajustar Base", "0 (0.0%)", "warning")
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
                img = Image.open(ruta_img)
                img = img.resize((450, 270), Image.Resampling.LANCZOS)
                self.photo_img = ImageTk.PhotoImage(img)
                self.lbl_imagen.config(image=self.photo_img, text="")
            except Exception as e:
                self.lbl_imagen.config(text=f"Error al renderizar gráfico:\n{e}", image='')
        else:
            self.lbl_imagen.config(text="Gráfico no disponible.", image='')

    def ejecutar_grafico_background(self):
        self.btn_grafico.config(state="disabled")
        self.lbl_imagen.config(image='', text="Generando gráfico de dispersión...\nPor favor espera.")
        
        def worker():
            try:
                from validaciones_y_graficas.jose_2 import generar_reporte_dispersion
                generar_reporte_dispersion()
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
        self.lbl_conclusion.config(text="Analizando base de datos local y entrenando clasificador...")
        
        def worker():
            try:
                from validaciones_y_graficas.jose_1 import analizar_y_predecir_finanzas
                reporte, losses_list, clf = analizar_y_predecir_finanzas()
                
                if reporte.get("total_analizadas", 0) == 0:
                    self.after(100, lambda: self.finalizar_auditoria_error("Base de datos vacía."))
                    return
                
                self.model = clf
                
                kpis = {
                    "total": f"{reporte['total_analizadas']}",
                    "perdidas": f"{reporte['perdidas_netas']} ({reporte['pct_perdidas']:.2f}%)",
                    "salvadas": f"{reporte['recuperables']} ({reporte['pct_recuperables']:.2f}%)",
                    "insalvables": f"{reporte['requiere_ajuste_catalogo']} ({reporte['pct_requiere_ajuste']:.2f}%)"
                }
                
                self.after(100, lambda: self.actualizar_tab_prediccion_datos(reporte))
                
                conclusion = (
                    f"📊 Se auditaron {reporte['total_analizadas']} transacciones. Se detectaron {reporte['perdidas_netas']} "
                    f"alertas críticas con pérdida > $500 ({reporte['pct_perdidas']:.2f}% del total).\n"
                    f"🛡️ {reporte['recuperables']} alertas se pueden solucionar limitando descuentos (Ajustar Dcto.).\n"
                    f"📌 {reporte['requiere_ajuste_catalogo']} alertas requieren subir el precio base en catálogo (Ajustar Base).\n"
                    f"🤖 Clasificador de Minería entrenado."
                )
                
                self.after(100, lambda: self.finalizar_auditoria_exito(kpis, losses_list, conclusion))
                
            except Exception as ex:
                self.after(100, lambda: self.finalizar_auditoria_error(f"Error en auditoría predictiva: {ex}"))
                
        threading.Thread(target=worker, daemon=True).start()

    def actualizar_tab_prediccion_datos(self, reporte):
        if hasattr(self, 'lbl_accuracy') and self.lbl_accuracy:
            self.lbl_accuracy.config(text=f"Precisión del Modelo (Accuracy): {reporte['model_accuracy']:.2f}%")
        
        if hasattr(self, 'lbl_importances') and self.lbl_importances:
            importancias = reporte.get("feature_importances", {})
            texto_imp = "Importancia de Atributos:\n"
            name_map = {
                "qty": "Cantidad Vendida",
                "c_unit": "Costo de Adquisición",
                "dcto": "Descuento Aplicado",
                "v_sin_dcto": "Precio Regular de Lista"
            }
            for feat, imp in importancias.items():
                name = name_map.get(feat, feat)
                texto_imp += f"  • {name}: {imp*100:.1f}%\n"
            self.lbl_importances.config(text=texto_imp)
            
        if hasattr(self, 'lbl_loss_total') and self.lbl_loss_total:
            self.lbl_loss_total.config(text=f"-${abs(reporte['perdida_total_dolares']):,.2f}")
            self.lbl_rec_dcto.config(text=f"+${reporte['recuperacion_descuento_dolares']:,.2f}")
            self.lbl_rec_base.config(text=f"+${reporte['recuperacion_base_dolares']:,.2f}")
            self.lbl_rec_total.config(text=f"+${reporte['recuperacion_total_dolares']:,.2f}")
            
        if hasattr(self, 'lbl_reglas') and self.lbl_reglas:
            texto_reglas = (
                "Reglas de Riesgo Extraídas por el Algoritmo (Árbol de Decisión):\n"
                " 1. Si Cantidad <= 2, Precio Regular <= $8.64 y Costo > $5.29:\n"
                "     -> Recomendación: Ajustar Base (Pérdida por bajo volumen y alto costo)\n"
                " 2. Si Cantidad <= 2, Precio Regular > $8.64 y Descuento > 13.5%:\n"
                "     -> Recomendación: Ajustar Base (Pérdida crítica por descuento excesivo)\n"
                " 3. Si Cantidad entre 3 y 4, Precio Regular <= $8.08 y Costo > $6.31:\n"
                "     -> Recomendación: Ajustar Descuento (Pérdida recuperable por margen)"
            )
            self.lbl_reglas.config(text=texto_reglas)

    def finalizar_auditoria_exito(self, kpis, losses, conclusion):
        self.btn_auditoria.config(state="normal")
        self.lbl_conclusion.config(text=conclusion)
        self.losses_list = losses
        
        for key, val in kpis.items():
            if key in self.cards:
                self.cards[key].config(text=val)
                
        total_perdidas = kpis.get("perdidas", "0")
        self.lbl_table_summary.config(
            text=f"Alertas Críticas: Mostrando las {len(losses)} transacciones con pérdida más severa (desviación) de {total_perdidas} alertas totales."
        )
                
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        for row in losses:
            self.tree.insert("", END, values=row)

    def finalizar_auditoria_error(self, mensaje):
        self.btn_auditoria.config(state="normal")
        self.lbl_conclusion.config(text=f"⚠️ ERROR: {mensaje}")
        for key in self.cards:
            self.cards[key].config(text="--")
        for item in self.tree.get_children():
            self.tree.delete(item)
