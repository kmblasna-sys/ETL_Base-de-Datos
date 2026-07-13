import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *

# Agregar el directorio base al sys.path para importaciones relativas
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "Conexion"))

try:
    from Conexion.conexion import obtener_conexion
except ImportError:
    obtener_conexion = None

# ==============================================================================
# MÓDULOS / PANELES MOCKUP PARA CADA INTEGRANTE DEL EQUIPO
# ==============================================================================

class LogisticaPanel(tb.Frame):
    """
    3.6.2 Panel de Gestión y Simulación de Capacidad Logística (Martin & David)
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, padding=20, **kwargs)
        
        # Encabezado
        tb.Label(
            self, 
            text="3.6.2 Gestión y Simulación de Capacidad Logística", 
            font=("Helvetica", 14, "bold"),
            bootstyle="primary"
        ).pack(anchor=W, pady=(0, 5))
        
        tb.Label(
            self, 
            text="Responsables: Martin & David", 
            font=("Helvetica", 10, "italic"),
            bootstyle="secondary"
        ).pack(anchor=W, pady=(0, 20))
        
        # Tarjeta informativa principal
        card = tb.Frame(self, bootstyle="light", padding=20)
        card.pack(fill=BOTH, expand=YES)
        
        tb.Label(
            card,
            text="Espacio Asignado para el Módulo de Capacidad Logística",
            font=("Helvetica", 12, "bold")
        ).pack(anchor=W, pady=(0, 10))
        
        desc = (
            "En esta sección se integrarán:\n"
            "• Mapas visuales de ocupación por almacén.\n"
            "• Simulador de entrada de nuevos lotes para predecir saturación (> 85% o > 95%).\n"
            "• Reglas de clasificación del modelo predictivo (árbol de decisión/scikit-learn)."
        )
        tb.Label(card, text=desc, font=("Helvetica", 10), justify=LEFT).pack(anchor=W, pady=10)
        
        # Simulación de elementos gráficos futuros
        placeholder_canvas = tb.Frame(card, height=200, bootstyle="secondary")
        placeholder_canvas.pack(fill=X, pady=15)
        tb.Label(
            placeholder_canvas, 
            text="[ Visualización de Capacidad y Alertas de Ocupación ]", 
            font=("Helvetica", 10, "bold"),
            foreground="white"
        ).place(relx=0.5, rely=0.5, anchor=CENTER)


class VencimientosPanel(tb.Frame):
    """
    3.6.3 Panel de Auditoría y Rotación de Stock Crítico (Laurente)
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, padding=20, **kwargs)
        
        tb.Label(
            self, 
            text="3.6.3 Auditoría y Rotación de Stock Crítico", 
            font=("Helvetica", 14, "bold"),
            bootstyle="info"
        ).pack(anchor=W, pady=(0, 5))
        
        tb.Label(
            self, 
            text="Responsable: Laurente", 
            font=("Helvetica", 10, "italic"),
            bootstyle="secondary"
        ).pack(anchor=W, pady=(0, 20))
        
        card = tb.Frame(self, bootstyle="light", padding=20)
        card.pack(fill=BOTH, expand=YES)
        
        tb.Label(
            card,
            text="Espacio Asignado para el Módulo de Control de Vencimientos",
            font=("Helvetica", 12, "bold")
        ).pack(anchor=W, pady=(0, 10))
        
        desc = (
            "En esta sección se integrarán:\n"
            "• Grillas/tablas de lotes activos con prioridad de rotación (Crítico, Alerta, Estable).\n"
            "• Filtros dinámicos por rango de días de vencimiento.\n"
            "• Botón disparador de salida prioritaria de stock."
        )
        tb.Label(card, text=desc, font=("Helvetica", 10), justify=LEFT).pack(anchor=W, pady=10)
        
        placeholder_canvas = tb.Frame(card, height=200, bootstyle="secondary")
        placeholder_canvas.pack(fill=X, pady=15)
        tb.Label(
            placeholder_canvas, 
            text="[ Tabla de Stock Crítico y Control de Rotación ]", 
            font=("Helvetica", 10, "bold"),
            foreground="white"
        ).place(relx=0.5, rely=0.5, anchor=CENTER)


class MargenesPanel(tb.Frame):
    """
    3.6.4 Panel de Control de Precios y Auditoría Financiera (Jose)
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, padding=20, **kwargs)
        
        tb.Label(
            self, 
            text="3.6.4 Control de Precios y Auditoría Financiera", 
            font=("Helvetica", 14, "bold"),
            bootstyle="success"
        ).pack(anchor=W, pady=(0, 5))
        
        tb.Label(
            self, 
            text="Responsable: Jose", 
            font=("Helvetica", 10, "italic"),
            bootstyle="secondary"
        ).pack(anchor=W, pady=(0, 20))
        
        card = tb.Frame(self, bootstyle="light", padding=20)
        card.pack(fill=BOTH, expand=YES)
        
        tb.Label(
            card,
            text="Espacio Asignado para el Módulo Financiero",
            font=("Helvetica", 12, "bold")
        ).pack(anchor=W, pady=(0, 10))
        
        desc = (
            "En esta sección se integrarán:\n"
            "• Auditoría de productos con margen base inferior al 5%.\n"
            "• Simulador de precios sugeridos de venta según el costo actual de adquisición.\n"
            "• Análisis de pérdidas transaccionales y rentabilidad."
        )
        tb.Label(card, text=desc, font=("Helvetica", 10), justify=LEFT).pack(anchor=W, pady=10)
        
        placeholder_canvas = tb.Frame(card, height=200, bootstyle="secondary")
        placeholder_canvas.pack(fill=X, pady=15)
        tb.Label(
            placeholder_canvas, 
            text="[ Auditoría de Precios y Margen de Rentabilidad ]", 
            font=("Helvetica", 10, "bold"),
            foreground="white"
        ).place(relx=0.5, rely=0.5, anchor=CENTER)


class PromocionesPanel(tb.Frame):
    """
    3.6.5 Panel de Simulación y Control de Ofertas Vigentes (Andrea)
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, padding=20, **kwargs)
        
        tb.Label(
            self, 
            text="3.6.5 Simulación y Control de Ofertas Vigentes", 
            font=("Helvetica", 14, "bold"),
            bootstyle="warning"
        ).pack(anchor=W, pady=(0, 5))
        
        tb.Label(
            self, 
            text="Responsable: Andrea", 
            font=("Helvetica", 10, "italic"),
            bootstyle="secondary"
        ).pack(anchor=W, pady=(0, 20))
        
        card = tb.Frame(self, bootstyle="light", padding=20)
        card.pack(fill=BOTH, expand=YES)
        
        tb.Label(
            card,
            text="Espacio Asignado para el Módulo de Ofertas y Promociones",
            font=("Helvetica", 12, "bold")
        ).pack(anchor=W, pady=(0, 10))
        
        desc = (
            "En esta sección se integrarán:\n"
            "• Cronograma visual interactivo de campañas promocionales activas.\n"
            "• Simulador de ofertas para predecir traslapes temporales antes de ser aprobadas.\n"
            "• Detección de anomalías en descuentos y consistencia promocional."
        )
        tb.Label(card, text=desc, font=("Helvetica", 10), justify=LEFT).pack(anchor=W, pady=10)
        
        placeholder_canvas = tb.Frame(card, height=200, bootstyle="secondary")
        placeholder_canvas.pack(fill=X, pady=15)
        tb.Label(
            placeholder_canvas, 
            text="[ Línea de Tiempo de Campañas y Detector de Traslapes ]", 
            font=("Helvetica", 10, "bold"),
            foreground="white"
        ).place(relx=0.5, rely=0.5, anchor=CENTER)


# ==============================================================================
# CONTENEDOR PRINCIPAL Y NAVEGACIÓN CENTRAL (3.6.1 - Martin & David)
# ==============================================================================

class WalmartContainerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Walmart Retail - Sistema Integrado de Gestión")
        self.root.geometry("1200x750")
        self.root.minsize(950, 600)
        
        self.crear_layout()
        self.verificar_conexion_db()
        
        # Cargar panel por defecto (Logística)
        self.mostrar_panel("logistica", LogisticaPanel)

    def crear_layout(self):
        # Contenedor Horizontal Principal (Sidebar + Contenido)
        self.main_layout = tb.Frame(self.root)
        self.main_layout.pack(fill=BOTH, expand=YES)
        
        # 1. SIDEBAR (Panel de Navegación Izquierdo)
        # Usamos un estilo de sidebar claro y limpio para un look moderno y minimalista
        self.sidebar = tb.Frame(self.main_layout, width=280, bootstyle="light", padding=20)
        self.sidebar.pack(fill=Y, side=LEFT)
        self.sidebar.pack_propagate(False)
        
        # Logotipo / Encabezado del Sistema
        tb.Label(
            self.sidebar, 
            text="WALMART RETAIL", 
            font=("Helvetica", 14, "bold"), 
            bootstyle="primary"
        ).pack(anchor=W, pady=(10, 5))
        
        tb.Label(
            self.sidebar, 
            text="Sistema de Integración (S13)", 
            font=("Helvetica", 9), 
            bootstyle="secondary"
        ).pack(anchor=W, pady=(0, 25))
        
        tb.Separator(self.sidebar, bootstyle="secondary").pack(fill=X, pady=(0, 20))
        
        # Botones de navegación planos (sin bordes) para evitar saturación visual
        self.nav_buttons = {}
        
        menu_items = [
            ("logistica", "📊  Capacidad Logística", LogisticaPanel),
            ("vencimientos", "📅  Stock y Vencimientos", VencimientosPanel),
            ("margenes", "💰  Control Financiero", MargenesPanel),
            ("promociones", "🏷️  Gestión de Ofertas", PromocionesPanel)
        ]
        
        for key, text, panel_cls in menu_items:
            btn = tb.Button(
                self.sidebar, 
                text=text, 
                bootstyle="secondary-link", 
                padding=(15, 10),
                command=lambda k=key, cls=panel_cls: self.mostrar_panel(k, cls)
            )
            btn.pack(fill=X, pady=4)
            self.nav_buttons[key] = btn
            
        # Pie de página del sidebar
        tb.Label(
            self.sidebar, 
            text="3.6.1 Contenedor Principal", 
            font=("Helvetica", 8, "italic"), 
            bootstyle="secondary"
        ).pack(side=BOTTOM, pady=10)
        
        # 2. CONTENEDOR DE CONTENIDO (Derecha)
        self.content_container = tb.Frame(self.main_layout, padding=10)
        self.content_container.pack(fill=BOTH, expand=YES, side=RIGHT)
        
        # Frame donde se montarán dinámicamente las pestañas
        self.active_frame = None
        
        # 3. BARRA DE ESTADO CENTRALIZADA (Bottom)
        self.status_bar = tb.Frame(self.root, height=35, bootstyle="light", padding=(15, 6))
        self.status_bar.pack(fill=X, side=BOTTOM)
        
        self.lbl_status_icon = tb.Label(
            self.status_bar, 
            text="🔌 Comprobando enlace...", 
            font=("Helvetica", 9, "bold"),
            bootstyle="secondary"
        )
        self.lbl_status_icon.pack(side=LEFT)
        
        self.lbl_db_details = tb.Label(
            self.status_bar, 
            text="MySQL: Desconectado", 
            font=("Helvetica", 9),
            bootstyle="secondary"
        )
        self.lbl_db_details.pack(side=RIGHT)
 
    def verificar_conexion_db(self):
        """
        Verifica dinámicamente la conexión a la base de datos centralizada de MySQL.
        """
        if not obtener_conexion:
            self.lbl_status_icon.config(text="⚠️ Error: Módulo de conexión no importado.", foreground="#c0392b")
            self.lbl_db_details.config(text="Servicio Desconectado", foreground="#c0392b")
            return
            
        conn = obtener_conexion()
        if conn:
            db_name = conn.database
            # Verdes oscuros legibles sobre fondo gris claro
            self.lbl_status_icon.config(text="🟢 Conexión Activa con Base de Datos", foreground="#27ae60")
            self.lbl_db_details.config(text=f"Servidor: localhost | Schema: {db_name}", foreground="#27ae60")
            conn.close()
        else:
            self.lbl_status_icon.config(text="🔴 Sin Conexión a la Base de Datos", foreground="#c0392b")
            self.lbl_db_details.config(text="Verifica la configuración del servidor MySQL", foreground="#c0392b")
 
    def mostrar_panel(self, key, panel_class):
        """
        Cambia dinámicamente el panel activo en el contenedor de contenido.
        """
        # Desactivar estilos de botón previos y resaltar el seleccionado
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.config(bootstyle="primary") # Sólido primario cuando está activo
            else:
                btn.config(bootstyle="secondary-link") # Plano gris cuando está inactivo
                
        # Limpiar contenedor de contenido anterior
        if self.active_frame:
            self.active_frame.destroy()
            
        # Instanciar el nuevo panel
        self.active_frame = panel_class(self.content_container)
        self.active_frame.pack(fill=BOTH, expand=YES)


if __name__ == "__main__":
    # Inicialización del tema "flatly"
    app_style = tb.Style(theme="flatly")
    root = app_style.master
    app = WalmartContainerApp(root)
    root.mainloop()
