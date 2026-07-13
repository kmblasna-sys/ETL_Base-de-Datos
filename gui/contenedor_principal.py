import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *

# === CAMBIO CLAVE: Importamos el módulo externo de Laurente ===
from PanelLaurente import PanelLaurente  
from tab_jose import MargenesPanel
from panel_simulacion_ofertas import PanelSimulacionOfertas

# Agregar el directorio base al sys.path para importaciones relativas
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "Conexion"))

try:
    from Conexion.conexion import obtener_conexion
except ImportError:
    obtener_conexion = None

# ==============================================================================
# MÓDULOS / PANELES MOCKUP RESTANTES
# ==============================================================================

class LogisticaPanel(tb.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, padding=20, **kwargs)
        tb.Label(self, text="3.6.2 Gestión y Simulación de Capacidad Logística", font=("Helvetica", 14, "bold"), bootstyle="primary").pack(anchor=W, pady=(0, 5))
        card = tb.Frame(self, bootstyle="light", padding=20)
        card.pack(fill=BOTH, expand=YES)
        tb.Label(card, text="[ Módulo de Capacidad Logística - Martin & David ]", font=("Helvetica", 10, "bold")).pack(pady=50)

# NOTA: Se eliminó la clase duplicada/mockup VencimientosPanel de aquí, ya que ahora usamos la importada.

#class MargenesPanel(tb.Frame):
    #def __init__(self, master, **kwargs):
        #super().__init__(master, padding=20, **kwargs)
        #tb.Label(self, text="3.6.4 Control de Precios y Auditoría Financiera", font=("Helvetica", 14, "bold"), bootstyle="success").pack(anchor=W, pady=(0, 5))
        #card = tb.Frame(self, bootstyle="light", padding=20)
        #card.pack(fill=BOTH, expand=YES)
        #tb.Label(card, text="[ Módulo Financiero - Jose ]", font=("Helvetica", 10, "bold")).pack(pady=50)

#class PromocionesPanel(tb.Frame):
    #def __init__(self, master, **kwargs):
        #super().__init__(master, padding=20, **kwargs)
        #tb.Label(self, text="3.6.5 Simulación y Control de Ofertas Vigentes", font=("Helvetica", 14, "bold"), bootstyle="warning").pack(anchor=W, pady=(0, 5))
        #card = tb.Frame(self, bootstyle="light", padding=20)
        #card.pack(fill=BOTH, expand=YES)
        #tb.Label(card, text="[ Módulo de Ofertas y Promociones - Andrea ]", font=("Helvetica", 10, "bold")).pack(pady=50)


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
        
        self.mostrar_panel("logistica", LogisticaPanel)

    def crear_layout(self):
        self.main_layout = tb.Frame(self.root)
        self.main_layout.pack(fill=BOTH, expand=YES)
        
        # 1. SIDEBAR
        self.sidebar = tb.Frame(self.main_layout, width=280, bootstyle="light", padding=20)
        self.sidebar.pack(fill=Y, side=LEFT)
        self.sidebar.pack_propagate(False)
        
        tb.Label(self.sidebar, text="WALMART RETAIL", font=("Helvetica", 14, "bold"), bootstyle="primary").pack(anchor=W, pady=(10, 5))
        tb.Label(self.sidebar, text="Sistema de Integración (S13)", font=("Helvetica", 9), bootstyle="secondary").pack(anchor=W, pady=(0, 25))
        tb.Separator(self.sidebar, bootstyle="secondary").pack(fill=X, pady=(0, 20))
        
        self.nav_buttons = {}
        
        # === CAMBIO CLAVE: Vinculamos el botón a la clase 'PanelLaurente' que importamos del otro archivo ===
        menu_items = [
            ("logistica", "📊  Capacidad Logística", LogisticaPanel),
            ("vencimientos", "📅  Stock y Vencimientos", PanelLaurente), # <-- Vinculación directa al módulo externo
            ("margenes", "💰  Control Financiero", MargenesPanel),
            ("promociones", "🏷️  Gestión de Ofertas", PanelSimulacionOfertas)
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
            
        tb.Label(self.sidebar, text="3.6.1 Contenedor Principal", font=("Helvetica", 8, "italic"), bootstyle="secondary").pack(side=BOTTOM, pady=10)
        
        # 2. CONTENEDOR DE CONTENIDO
        self.content_container = tb.Frame(self.main_layout, padding=10)
        self.content_container.pack(fill=BOTH, expand=YES, side=RIGHT)
        self.active_frame = None
        
        # 3. BARRA DE ESTADO CENTRALIZADA
        self.status_bar = tb.Frame(self.root, height=35, bootstyle="light", padding=(15, 6))
        self.status_bar.pack(fill=X, side=BOTTOM)
        
        self.lbl_status_icon = tb.Label(self.status_bar, text="🔌 Comprobando enlace...", font=("Helvetica", 9, "bold"), bootstyle="secondary")
        self.lbl_status_icon.pack(side=LEFT)
        
        self.lbl_db_details = tb.Label(self.status_bar, text="MySQL: Desconectado", font=("Helvetica", 9), bootstyle="secondary")
        self.lbl_db_details.pack(side=RIGHT)
 
    def verificar_conexion_db(self):
        if not obtener_conexion:
            self.lbl_status_icon.config(text="⚠️ Error: Módulo de conexión no importado.", foreground="#c0392b")
            self.lbl_db_details.config(text="Servicio Desconectado", foreground="#c0392b")
            return
            
        conn = obtener_conexion()
        if conn:
            db_name = conn.database
            self.lbl_status_icon.config(text="🟢 Conexión Activa con Base de Datos", foreground="#27ae60")
            self.lbl_db_details.config(text=f"Servidor: localhost | Schema: {db_name}", foreground="#27ae60")
            conn.close()
        else:
            self.lbl_status_icon.config(text="🔴 Sin Conexión a la Base de Datos", foreground="#c0392b")
            self.lbl_db_details.config(text="Verifica la configuración del servidor MySQL", foreground="#c0392b")
 
    def mostrar_panel(self, key, panel_class):
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.config(bootstyle="primary")
            else:
                btn.config(bootstyle="secondary-link")
                
        if self.active_frame:
            self.active_frame.destroy()
            
        # Instanciar el nuevo panel importado dinámicamente
        self.active_frame = panel_class(self.content_container)
        self.active_frame.pack(fill=BOTH, expand=YES)


if __name__ == "__main__":
    app_style = tb.Style(theme="flatly")
    root = app_style.master
    app = WalmartContainerApp(root)
    root.mainloop()