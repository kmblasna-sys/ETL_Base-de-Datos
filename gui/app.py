import sys
import os
import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *

# Agregar el directorio base al sys.path para importaciones
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "Conexion"))

try:
    from Conexion.conexion import obtener_conexion
except ImportError:
    obtener_conexion = None

# Lista de tablas en Mineria_BD
TABLAS_BD = [
    "Tipo_Promocion",
    "Producto",
    "Categoria",
    "Venta",
    "Compra",
    "Ubicacion",
    "PROMOCION",
    "Prod_Prom",
    "Historial_Comercial",
    "Almacen",
    "Lotes_de_Inventario",
    "DetalleVenta",
    "Detalle_Compra"
]

class WalmartExplorerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Walmart Retail - Explorador de Base de Datos")
        self.root.geometry("1150x720")
        self.root.minsize(900, 580)
        
        # Datos en caché para búsqueda/filtrado
        self.columnas_actuales = []
        self.datos_actuales = []
        self.tabla_seleccionada = None
        
        self.crear_layout()
        self.verificar_conexion()
        
        # Cargar la primera tabla por defecto si hay conexión
        if obtener_conexion:
            self.root.after(100, lambda: self.seleccionar_tabla(TABLAS_BD[0]))

    def crear_layout(self):
        # --- HEADER BANNER ---
        header_frame = tb.Frame(self.root, bootstyle=PRIMARY, padding=12)
        header_frame.pack(fill=X, side=TOP)
        
        title_label = tb.Label(
            header_frame, 
            text="📊  WALMART RETAIL - EXPLORADOR DE BASE DE DATOS", 
            font=("Helvetica", 14, "bold"), 
            foreground="white"
        )
        title_label.pack(side=LEFT)
        
        # Selector de Tema Dinámico
        theme_frame = tb.Frame(header_frame, bootstyle=PRIMARY)
        theme_frame.pack(side=RIGHT, padx=(10, 0))
        
        tb.Label(theme_frame, text="🎨 Tema:", font=("Helvetica", 10, "bold"), foreground="white").pack(side=LEFT, padx=(0, 5))
        
        # Obtener todos los temas disponibles en ttkbootstrap
        self.theme_combobox = tb.Combobox(
            theme_frame, 
            values=tb.Style.get_instance().theme_names(), 
            state="readonly", 
            width=14,
            font=("Helvetica", 10)
        )
        self.theme_combobox.set(tb.Style.get_instance().theme_use())
        self.theme_combobox.pack(side=LEFT)
        self.theme_combobox.bind("<<ComboboxSelected>>", self.cambiar_tema)

        # --- CUERPO PRINCIPAL ---
        main_paned = tb.Panedwindow(self.root, orient=HORIZONTAL)
        main_paned.pack(fill=BOTH, expand=YES, padx=12, pady=12)
        
        # Panel Izquierdo: Lista de Tablas (Navegación)
        left_panel = tb.Frame(main_paned, padding=5, width=270)
        left_panel.pack_propagate(False)
        main_paned.add(left_panel, weight=1)
        
        tb.Label(
            left_panel, 
            text="Tablas de Base de Datos", 
            font=("Helvetica", 11, "bold"), 
            anchor=W
        ).pack(fill=X, pady=(0, 10))
        
        # Contenedor con scroll para los botones de las tablas
        scroll_canvas = tk.Canvas(left_panel, highlightthickness=0)
        scrollbar_buttons = tb.Scrollbar(left_panel, orient=VERTICAL, command=scroll_canvas.yview)
        scrollable_frame = tb.Frame(scroll_canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))
        )
        scroll_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=240)
        scroll_canvas.configure(yscrollcommand=scrollbar_buttons.set)
        
        scroll_canvas.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar_buttons.pack(side=RIGHT, fill=Y)
        
        # Agregar botones de las tablas con bootstyle outline para mejor visualización
        self.botones_tablas = {}
        for tabla in TABLAS_BD:
            btn = tb.Button(
                scrollable_frame, 
                text=f"📄  {tabla}", 
                bootstyle="secondary-outline", 
                padding=(12, 8),
                command=lambda t=tabla: self.seleccionar_tabla(t)
            )
            btn.pack(fill=X, pady=3)
            self.botones_tablas[tabla] = btn
            
        # Panel Derecho: Visualizador de Datos
        right_panel = tb.Frame(main_paned, padding=5)
        main_paned.add(right_panel, weight=4)
        
        # Cabecera del Panel Derecho: Nombre de Tabla y Buscador
        right_header = tb.Frame(right_panel)
        right_header.pack(fill=X, pady=(0, 10))
        
        self.lbl_nombre_tabla = tb.Label(
            right_header, 
            text="Selecciona una tabla de la lista", 
            font=("Helvetica", 12, "bold")
        )
        self.lbl_nombre_tabla.pack(side=LEFT)
        
        # Buscador en vivo
        search_frame = tb.Frame(right_header)
        search_frame.pack(side=RIGHT)
        
        tb.Label(search_frame, text="🔍 Filtrar:", font=("Helvetica", 10)).pack(side=LEFT, padx=(0, 5))
        self.var_buscar = tk.StringVar()
        self.var_buscar.trace_add("write", self.filtrar_datos)
        self.ent_buscar = tb.Entry(search_frame, textvariable=self.var_buscar, width=28)
        self.ent_buscar.pack(side=LEFT)
        
        # Contenedor del Treeview con Scrollbars
        self.tree_frame = tb.Frame(right_panel, bootstyle=LIGHT)
        self.tree_frame.pack(fill=BOTH, expand=YES)
        
        self.tree = None
        self.mostrar_tabla_vacia("Selecciona una tabla para comenzar.")
        
        # --- BARRA DE ESTADO ---
        self.status_bar = tb.Frame(self.root, bootstyle=LIGHT, padding=6)
        self.status_bar.pack(fill=X, side=BOTTOM)
        
        self.lbl_status = tb.Label(
            self.status_bar, 
            text="Iniciando...", 
            font=("Helvetica", 9)
        )
        self.lbl_status.pack(side=LEFT)
        
        self.lbl_db_info = tb.Label(
            self.status_bar, 
            text="MySQL", 
            font=("Helvetica", 9, "bold")
        )
        self.lbl_db_info.pack(side=RIGHT)

    def cambiar_tema(self, event):
        nuevo_tema = self.theme_combobox.get()
        tb.Style.get_instance().theme_use(nuevo_tema)
        self.lbl_status.config(text=f"Tema cambiado a: {nuevo_tema}.")

    def verificar_conexion(self):
        if not obtener_conexion:
            self.lbl_status.config(text="⚠️ Conector de base de datos no configurado.", foreground="red")
            self.lbl_db_info.config(text="Desconectado", foreground="red")
            return False
            
        conn = obtener_conexion()
        if conn:
            db_name = conn.database
            self.lbl_status.config(text="🟢 Conexión exitosa con la base de datos MySQL.", foreground="#2ecc71")
            self.lbl_db_info.config(text=f"Base de Datos: {db_name}", foreground="#2ecc71")
            conn.close()
            return True
        else:
            self.lbl_status.config(text="🔴 Error de enlace con el servidor MySQL.", foreground="red")
            self.lbl_db_info.config(text="Desconectado", foreground="red")
            return False

    def seleccionar_tabla(self, nombre_tabla):
        self.tabla_seleccionada = nombre_tabla
        self.var_buscar.set("") # Limpiar buscador
        
        # Resaltar botón seleccionado y restaurar los demás
        for t, btn in self.botones_tablas.items():
            if t == nombre_tabla:
                btn.config(bootstyle="primary")
            else:
                btn.config(bootstyle="secondary-outline")
                
        self.lbl_nombre_tabla.config(text=f"Tabla: {nombre_tabla} (Cargando...)")
        self.root.update_idletasks()
        
        # Cargar datos
        self.cargar_datos(nombre_tabla)

    def cargar_datos(self, nombre_tabla):
        conn = obtener_conexion()
        if not conn:
            self.mostrar_tabla_vacia("Error: No se pudo conectar a la base de datos.")
            return
            
        cursor = conn.cursor()
        try:
            # Obtener columnas de la tabla
            cursor.execute(f"DESCRIBE {nombre_tabla};")
            self.columnas_actuales = [row[0] for row in cursor.fetchall()]
            
            # Obtener registros (límite 500 para velocidad en UI)
            cursor.execute(f"SELECT * FROM {nombre_tabla} LIMIT 500;")
            self.datos_actuales = cursor.fetchall()
            
            self.renderizar_tabla(nombre_tabla)
        except Exception as e:
            self.mostrar_tabla_vacia(f"Error al leer datos de la tabla: {e}")
        finally:
            cursor.close()
            conn.close()

    def renderizar_tabla(self, nombre_tabla):
        # Limpiar visualizador
        for widget in self.tree_frame.winfo_children():
            widget.destroy()
            
        if not self.columnas_actuales:
            self.mostrar_tabla_vacia("La tabla está vacía o no tiene columnas.")
            return

        # Crear barras de desplazamiento
        scroll_y = tb.Scrollbar(self.tree_frame, orient=VERTICAL)
        scroll_x = tb.Scrollbar(self.tree_frame, orient=HORIZONTAL)
        
        # Crear Treeview usando estilo primario estándar de ttkbootstrap
        self.tree = tb.Treeview(
            self.tree_frame, 
            columns=self.columnas_actuales, 
            show="headings", 
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
            bootstyle="primary"
        )
        
        scroll_y.config(command=self.tree.yview)
        scroll_x.config(command=self.tree.xview)
        
        # Configurar cabeceras de columnas
        for col in self.columnas_actuales:
            self.tree.heading(col, text=col, anchor=W)
            self.tree.column(col, width=max(130, len(col) * 12), minwidth=110, stretch=True)
            
        # Rellenar datos
        self.rellenar_treeview(self.datos_actuales)
        
        # Empaquetar componentes
        scroll_y.pack(side=RIGHT, fill=Y)
        scroll_x.pack(side=BOTTOM, fill=X)
        self.tree.pack(fill=BOTH, expand=YES)
        
        self.lbl_nombre_tabla.config(text=f"Tabla: {nombre_tabla} ({len(self.datos_actuales)} filas cargadas)")
        self.lbl_status.config(text=f"Visualizando tabla: {nombre_tabla}.", foreground="black")

    def rellenar_treeview(self, filas):
        # Limpiar Treeview
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        for fila in filas:
            valores_limpios = []
            for val in fila:
                if val is None:
                    valores_limpios.append("NULL")
                elif isinstance(val, (datetime.date, datetime.datetime)):
                    valores_limpios.append(val.strftime('%Y-%m-%d'))
                else:
                    valores_limpios.append(str(val))
                    
            self.tree.insert("", END, values=valores_limpios)

    def filtrar_datos(self, *args):
        termino = self.var_buscar.get().lower().strip()
        if not self.tree:
            return
            
        if not termino:
            self.rellenar_treeview(self.datos_actuales)
            self.lbl_nombre_tabla.config(text=f"Tabla: {self.tabla_seleccionada} ({len(self.datos_actuales)} filas)")
            return
            
        filas_filtradas = []
        for fila in self.datos_actuales:
            match = False
            for campo in fila:
                if campo is not None and termino in str(campo).lower():
                    match = True
                    break
            if match:
                filas_filtradas.append(fila)
                
        self.rellenar_treeview(filas_filtradas)
        self.lbl_nombre_tabla.config(text=f"Tabla: {self.tabla_seleccionada} ({len(filas_filtradas)} de {len(self.datos_actuales)} encontradas)")

    def mostrar_tabla_vacia(self, mensaje):
        for widget in self.tree_frame.winfo_children():
            widget.destroy()
        lbl = tb.Label(self.tree_frame, text=mensaje, font=("Helvetica", 10), anchor=CENTER, padding=100)
        lbl.pack(fill=BOTH, expand=YES)

if __name__ == "__main__":
    # Iniciamos con el tema "flatly" por defecto
    app_style = tb.Style(theme="flatly")
    root = app_style.master
    app = WalmartExplorerApp(root)
    root.mainloop()
