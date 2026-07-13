"""
Panel de Simulación y Control de Ofertas Vigentes
--------------------------------------------------
Módulo: panel_simulacion_ofertas.py
Proyecto: Auditoría y Simulación Promocional - Walmart (Mineria_BD)

Componentes:
1. Cronograma visual (Gantt) de las campañas activas, resaltando en rojo
   las promociones que ya presentan traslape (misma lógica de la Regla 1).
2. Simulador de ofertas: antes de registrar una nueva promoción, cruza el
   rango propuesto contra Prod_Prom/PROMOCION para detectar traslapes y
   estima si el margen resultante caería bajo el 5% mínimo.
"""

import sys
import os
from datetime import date, datetime

# [CORRECCIÓN DPI EN WINDOWS]
# Sin esto, en pantallas con escalado (125%/150%, muy común en laptops),
# Windows re-escala la ventana de Tkinter sin que la app lo sepa, y el
# contenido termina renderizándose más ancho de lo reportado, empujando
# paneles fuera del área visible (justo lo que causaba que el Simulador
# no apareciera). Debe ejecutarse ANTES de crear cualquier ventana.
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

        # 2. IMPORTANTE: Empaquetamos PRIMERO el simulador a la derecha
        self.frame_simulador.pack(side=RIGHT, fill=Y, padx=10, pady=10)

        # 3. Empaquetamos al FINAL el cronograma para que tome TODO el espacio restante a la izquierda
        self.frame_cronograma.pack(side=LEFT, fill=BOTH, expand=True, padx=10, pady=10)

        self._oferta_validada = None

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

        self._construir_cronograma()

    # ------------------------------------------------------------------
    # CRONOGRAMA VISUAL (GANTT)
    # ------------------------------------------------------------------
    def _obtener_promociones_activas(self):
        conexion = obtener_conexion()
        if conexion is None:
            return []
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT Id_promocion, Fecha_Inicio, Fecha_Finalizacion
            FROM PROMOCION
            WHERE Estado_Promocion = 'Activa' 
            ORDER BY Fecha_Inicio
        """)
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

    def _construir_cronograma(self):
        promociones = self._obtener_promociones_activas()
        conflictivas = self._detectar_traslapes(promociones)

        # 1. Mantener tamaño y proporciones originales
        figura = Figure(figsize=(6, 4.5), dpi=100)
        ax = figura.add_subplot(111)

        # Desactivar por completo los márgenes internos automáticos de Matplotlib en el eje X
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

        # 2. Configuración estándar de fechas
        import matplotlib.dates as mdates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        
        # 3. ELIMINACIÓN FORZADA DEL MARGEN IZQUIERDO
        if todas_las_fechas:
            fecha_min = min(todas_las_fechas)
            fecha_max = max(todas_las_fechas)
            
            import datetime
            margen_derecho = datetime.timedelta(days=20) # Espacio para que no se corten los nombres al final
            
            # Forzamos los límites estrictos por dos métodos para asegurar que Tkinter no los altere
            ax.set_xlim(fecha_min, fecha_max + margen_derecho)
            ax.set_xbound(lower=fecha_min, upper=fecha_max + margen_derecho)

        # Rotación diagonal de las fechas
        figura.autofmt_xdate()

        # Ajustes estéticos del contenedor
        ax.set_ylim(-0.5, len(promociones) - 0.5)
        ax.set_yticks([])
        ax.set_xlabel("Línea de Tiempo")
        ax.set_title(
            "Cronograma de Campañas Activas\n(rojo = traslape detectado)",
            fontsize=11, fontweight="bold"
        )
        ax.grid(axis="x", linestyle="--", alpha=0.4)
        
        # tight_layout ajusta los elementos internos
        figura.tight_layout()

        # Limpieza manual del frame para que el botón validar no altere nada
        for widget in self.frame_cronograma.winfo_children():
            widget.destroy()

        lienzo = FigureCanvasTkAgg(figura, master=self.frame_cronograma)
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

        self.boton_aprobar = ttk.Button(
            self.frame_simulador, text="Aprobar y Registrar",
            bootstyle=SUCCESS, state=DISABLED, command=self._registrar_oferta
        )
        self.boton_aprobar.pack(pady=10, fill=X)

    def _validar_oferta(self):
        errores = []

        # 1. Obtener strings limpios usando los nombres correctos de tus variables
        codigo_producto = self.entrada_producto.get().strip()
        fecha_inicio_str = self.entrada_inicio.get().strip()
        fecha_fin_str = self.entrada_fin.get().strip()
        
        # Limpiar descuento (quitar % si el usuario lo escribe)
        descuento_raw = self.entrada_descuento.get().strip().replace("%", "")
        stock_raw = self.entrada_stock.get().strip()

        # 2. Validación de campos vacíos (se mantiene igual, pero con las variables locales)
        if not all([codigo_producto, fecha_inicio_str, fecha_fin_str, descuento_raw, stock_raw]):
            self.etiqueta_resultado.config(
                text="⚠️ Todos los campos son obligatorios.", 
                bootstyle="danger"
            )
            return

        # ... (El resto de tus bloques try-except de conversión numérica y de fechas se quedan exactamente igual)

        # 3. Conversión segura de números
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

        # 4. Conversión segura de fechas
        try:
            from datetime import datetime
            fecha_inicio_dt = datetime.strptime(fecha_inicio_str, "%Y-%m-%d").date()
            fecha_fin_dt = datetime.strptime(fecha_fin_str, "%Y-%m-%d").date()
            
            if fecha_fin_dt < fecha_inicio_dt:
                errores.append("- La fecha de fin no puede ser anterior a la de inicio.")
        except ValueError:
            errores.append("- Formato de fecha incorrecto. Use AAAA-MM-DD (ej: 2026-07-15).")

        # ... (Toda tu lógica anterior de los bloques try-except)

        # 5. Mostrar los resultados específicos en la etiqueta de advertencia
        if errores:
            self.etiqueta_resultado.config(
                text="⛔ Errores detectados:\n" + "\n".join(errores), 
                bootstyle="danger"
            )
            self.boton_aprobar.config(state="disabled")
            self._oferta_validada = None  # Limpiamos si había algo previo
        else:
            # --- REEMPLAZA EL 'pass' CON ESTO ---
            # 1. Informar al usuario que todo está en orden
            self.etiqueta_resultado.config(
                text="✔ Oferta válida. Sin errores de formato.", 
                bootstyle="success"
            )
            
            # 2. HABILITAR EL BOTÓN DE REGISTRO
            self.boton_aprobar.config(state="normal")
            
            # 3. Guardar los datos limpios en la variable de la clase para usarlos al registrar
            id_tipo = int(self.combo_tipo.get().split(" - ")[0]) if self.combo_tipo.get() else None
            self._oferta_validada = (
                codigo_producto, 
                id_tipo, 
                fecha_inicio_dt, 
                fecha_fin_dt, 
                descuento_val, 
                stock_val
            )

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
        except Exception as error:
            conexion.rollback()
            self.etiqueta_resultado.config(text=f"⚠ Error al registrar: {error}", bootstyle=DANGER)
        finally:
            cursor.close()
            conexion.close()
            self.boton_aprobar.config(state=DISABLED)
            self._oferta_validada = None


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