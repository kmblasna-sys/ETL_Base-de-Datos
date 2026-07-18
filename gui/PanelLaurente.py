import os
import sys
import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *

# Agregar ruta base para importar validacion.py y Conexion
# PanelLaurente está en gui/, necesitamos la carpeta padre (codigo_bd/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Sube dos niveles: gui -> codigo_bd
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

IMPORT_ERROR_VALIDACION = None
try:
    from validaciones_y_graficas.validacion import obtener_lotes_perecederos
except Exception as e:
    obtener_lotes_perecederos = None
    IMPORT_ERROR_VALIDACION = str(e)


class PanelLaurenteApp(tb.Frame):
    def __init__(self, master):
        # master puede ser un Frame (cuando se usa dentro del contenedor)
        # o una ventana Tk (cuando se usa como app independiente)
        super().__init__(master, padding=0)
        
        self._datos = []
        self._datos_lotes = []

        self.crear_layout()

    def crear_layout(self):
        header = tb.Frame(self, bootstyle=PRIMARY, padding=12)
        header.pack(fill=X, side=TOP)

        tb.Label(header, text="📦 Panel de Vencimientos - Lotes en Riesgo", font=("Helvetica", 14, "bold"), foreground="white").pack(side=LEFT)
        tb.Button(header, text="🔄 Cargar datos", bootstyle="light", command=self.cargar_datos).pack(side=RIGHT)

        info_bar = tb.Frame(self, padding=10)
        info_bar.pack(fill=X)

        self.lbl_info = tb.Label(info_bar, text="Presiona 'Cargar datos' para mostrar la grilla y el gráfico.", font=("Helvetica", 10))
        self.lbl_info.pack(side=LEFT)

        filtros_frame = tb.Labelframe(self, text="Buscar por producto y revisar caducidad", padding=12)
        filtros_frame.pack(fill=X, padx=12, pady=(0, 8))

        row = tb.Frame(filtros_frame)
        row.pack(fill=X, pady=4)
        tb.Label(row, text="Buscar producto o código:", width=20).pack(side=LEFT)
        self.ent_busqueda = tb.Entry(row, width=30)
        self.ent_busqueda.pack(side=LEFT, padx=(0, 12))

        tb.Label(row, text="Criterio:", width=12).pack(side=LEFT)
        self.cmb_criterio = ttk.Combobox(row, state="readonly", values=["Todos", "Próximos a vencer (<= 180 días)", "Críticos (< 60 días)", "Vencidos / caducados"], width=28)
        self.cmb_criterio.current(0)
        self.cmb_criterio.pack(side=LEFT, padx=(0, 12))

        tb.Button(row, text="Aplicar búsqueda", bootstyle="success", command=self.aplicar_filtro).pack(side=LEFT)
        tb.Button(row, text="Ver gráfico", bootstyle="info", command=self.ver_grafico).pack(side=LEFT, padx=(10, 0))

        panel = tb.Frame(self, padding=12)
        panel.pack(fill=BOTH, expand=YES, padx=12, pady=(0, 8))

        self.tree = tb.Treeview(panel, columns=("lote", "codigo", "producto", "fecha_ingreso", "fecha_vencimiento", "dias_restantes", "prioridad", "capacidad", "ocupado"), show="headings", bootstyle="secondary", height=18)
        for col, text, width in [
            ("lote", "Número de Lote", 120),
            ("codigo", "Código", 120),
            ("producto", "Producto", 220),
            ("fecha_ingreso", "Fecha Ingreso", 110),
            ("fecha_vencimiento", "Fecha Vencimiento", 130),
            ("dias_restantes", "Días Restantes", 110),
            ("prioridad", "Prioridad", 110),
            ("capacidad", "Capacidad Total", 110),
            ("ocupado", "Espacio Ocupado", 110),
        ]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor=W)
        self.tree.pack(fill=BOTH, expand=YES, side=LEFT)

        scroll_y = tb.Scrollbar(panel, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side=LEFT, fill=Y)

        derecho = tb.Frame(self, padding=12)
        derecho.pack(fill=X, padx=12, pady=(0, 12))

        self.lbl_estado = tb.Label(derecho, text="Estado: pendiente de carga.", font=("Helvetica", 10, "bold"))
        self.lbl_estado.pack(anchor=W)

        tb.Button(derecho, text="🚨 Disparar salida prioritaria", bootstyle="danger", command=self.disparar_salida_prioritaria).pack(anchor=W, pady=(8, 0))

    def cargar_datos(self):
        if not obtener_lotes_perecederos:
            mensaje = "No se encontró la función de validación en validacion.py."
            if IMPORT_ERROR_VALIDACION:
                mensaje += f"\n\nDetalle: {IMPORT_ERROR_VALIDACION}"
            messagebox.showerror("Error", mensaje)
            return

        self._datos = obtener_lotes_perecederos()
        if not self._datos:
            self.lbl_info.config(text="No se encontraron datos de lotes perecederos o no hay conexión.")
            return

        self.lbl_info.config(text=f"Datos cargados: {len(self._datos)} lotes. Busca por nombre o código y aplica el criterio de caducidad.")
        self._datos_lotes = []
        self.mostrar_datos(self._datos)

    def mostrar_datos(self, datos):
        for item in self.tree.get_children():
            self.tree.delete(item)

        self._datos_lotes = []
        for fila in datos:
            lote = fila.get('Numero_Lote', '-')
            codigo = fila.get('Codigo_de_Producto', '-')
            producto = fila.get('Nombre_Producto', fila.get('Nombre', '-'))
            fecha_ingreso = fila.get('Fecha_ingreso')
            fecha_ingreso = fecha_ingreso.strftime('%Y-%m-%d') if hasattr(fecha_ingreso, 'strftime') else str(fecha_ingreso)
            fecha_vencimiento = fila.get('Fecha_Vencimiento')
            fecha_vencimiento = fecha_vencimiento.strftime('%Y-%m-%d') if hasattr(fecha_vencimiento, 'strftime') else str(fecha_vencimiento)
            dias = fila.get('Dias_Restantes', -1)
            prioridad = fila.get('Prioridad_Label', 'Normal')
            capacidad = fila.get('Capacidad_Total', '-')
            ocupado = fila.get('Espacio_ocupado', '-')
            item_id = self.tree.insert("", END, values=(lote, codigo, producto, fecha_ingreso, fecha_vencimiento, dias, prioridad, capacidad, ocupado))
            self._datos_lotes.append((item_id, lote, codigo, producto, dias, prioridad))

        self._aplicar_colores()

    def _aplicar_colores(self):
        self.tree.tag_configure('vencido', background='#d3d3d3')
        self.tree.tag_configure('critico', background='#f8d7da')
        self.tree.tag_configure('alerta', background='#fcf3cf')
        self.tree.tag_configure('normal', background='#d4edda')
        

        for item_id, lote, codigo, producto, dias, prioridad in self._datos_lotes:
            if prioridad == 'Vencido' or (isinstance(dias, (int, float)) and dias < 0):
                tag = 'vencido'
            elif prioridad == 'Crítico':
                tag = 'critico'
            elif prioridad == 'Alerta':
                tag = 'alerta'
            else:
                tag = 'normal'
            self.tree.item(item_id, tags=(tag,))

    def aplicar_filtro(self):
        if not self._datos:
            messagebox.showwarning("Filtro", "Primero carga los datos.")
            return

        texto_busqueda = self.ent_busqueda.get().strip().lower()
        criterio = self.cmb_criterio.get()

        datos_filtrados = []
        for fila in self._datos:
            codigo = str(fila.get('Codigo_de_Producto', '')).lower()
            nombre = str(fila.get('Nombre_Producto', fila.get('Nombre', ''))).lower()
            coincide = not texto_busqueda or texto_busqueda in codigo or texto_busqueda in nombre
            if not coincide:
                continue

            dias = fila.get('Dias_Restantes', -1)
            if criterio == 'Próximos a vencer (<= 180 días)':
                if dias < 0 or dias > 180:
                    continue
            elif criterio == 'Críticos (< 60 días)':
                if dias < 0 or dias >= 60:
                    continue
            elif criterio == 'Vencidos / caducados':
                if dias >= 0:
                    continue

            datos_filtrados.append(fila)

        if texto_busqueda:
            self.lbl_info.config(text=f"Mostrando {len(datos_filtrados)} lotes que coinciden con '{texto_busqueda}' y criterio '{criterio}'.")
        else:
            self.lbl_info.config(text=f"Mostrando {len(datos_filtrados)} lotes según el criterio '{criterio}'.")
        self.mostrar_datos(datos_filtrados)

    def ver_grafico(self):
        if not self._datos:
            messagebox.showwarning("Gráfico", "Carga los datos primero para ver el gráfico.")
            return

        valores = [max(0, fila.get('Dias_Restantes', 0)) for fila in self._datos if fila.get('Dias_Restantes') is not None]
        if not valores:
            messagebox.showwarning("Gráfico", "No hay datos válidos de días restantes para graficar.")
            return

        try:
            import matplotlib.pyplot as plt
            use_matplotlib = True
        except ImportError:
            use_matplotlib = False

        if use_matplotlib:
            plt.figure(figsize=(10, 5.5))
            plt.hist(valores, bins=30, color='#2c3e50', edgecolor='white', alpha=0.85)
            plt.axvline(x=60, color='#e74c3c', linestyle='--', linewidth=2, label='Crítico (<60 días)')
            plt.axvline(x=180, color='#f39c12', linestyle='--', linewidth=2, label='Alerta (60-180 días)')
            plt.title('Distribución de Días Restantes para Vencimiento')
            plt.xlabel('Días Restantes')
            plt.ylabel('Cantidad de lotes')
            plt.legend(loc='upper right')
            plt.tight_layout()
            plt.show()
            return

        # Fallback nativo a Tkinter cuando matplotlib no está instalado
        valores_ordenados = sorted(valores)
        bins = 15
        min_val = valores_ordenados[0]
        max_val = valores_ordenados[-1]
        if min_val == max_val:
            max_val = min_val + 1
        ancho_bin = (max_val - min_val) / bins
        if ancho_bin == 0:
            ancho_bin = 1

        conteos = [0] * bins
        for v in valores_ordenados:
            idx = int((v - min_val) // ancho_bin)
            if idx >= bins:
                idx = bins - 1
            conteos[idx] += 1

        top = tk.Toplevel(self.winfo_toplevel())
        top.title('Histograma de Días de Vencimiento')
        top.geometry('760x520')

        canvas = tk.Canvas(top, bg='white')
        canvas.pack(fill=BOTH, expand=YES)

        margin_x = 50
        margin_y = 40
        width = 680
        height = 420
        max_count = max(conteos) if conteos else 1

        canvas.create_text(margin_x + width / 2, 20, text='Histograma de Días Restantes para Vencimiento', font=('Helvetica', 12, 'bold'))
        canvas.create_text(16, margin_y + 10, text=f'Máximo: {max_count}', anchor='nw', font=('Helvetica', 9))

        for i, count in enumerate(conteos):
            x0 = margin_x + i * (width / bins) + 2
            x1 = margin_x + (i + 1) * (width / bins) - 2
            y1 = margin_y + height
            y0 = y1 - (count / max_count) * (height - 20)
            canvas.create_rectangle(x0, y0, x1, y1, fill='#2c3e50', outline='')
            if i % max(1, bins // 8) == 0 or i == bins - 1:
                etiqueta = str(int(min_val + i * ancho_bin))
                canvas.create_text((x0 + x1) / 2, y1 + 14, text=etiqueta, anchor='n', font=('Helvetica', 8))

        for linea in [60, 180]:
            if min_val <= linea <= max_val:
                x = margin_x + (linea - min_val) / (max_val - min_val) * width
                canvas.create_line(x, margin_y, x, margin_y + height, fill='#e74c3c' if linea == 60 else '#f39c12', dash=(4, 4))
                canvas.create_text(x + 4, margin_y + 12, text=f'{linea}', anchor='nw', font=('Helvetica', 8), fill='#000000')

        canvas.create_text(margin_x + 8, margin_y + height / 2, text='Frecuencia', angle=90, font=('Helvetica', 9))

    def disparar_salida_prioritaria(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning("Salida prioritaria", "Selecciona uno o más lotes.")
            return

        lotes = []
        vencidos = []
        for item in seleccion:
            valores = self.tree.item(item)['values']
            lote = valores[0]
            prioridad = valores[6] if len(valores) > 6 else ''
            dias = valores[5] if len(valores) > 5 else None
            try:
                dias = int(dias)
            except Exception:
                dias = None

            if prioridad == 'Vencido' or (dias is not None and dias < 0):
                vencidos.append(lote)
            else:
                lotes.append(lote)

        if vencidos:
            message = (
                f"No se puede aplicar salida prioritaria a los lotes vencidos: {', '.join(vencidos)}. "
                "Revise el stock vencido y gestione su disposición separadamente."
            )
            messagebox.showwarning("Restricción de salida prioritaria", message)
            if not lotes:
                return

        confirm = messagebox.askyesno("Confirmar salida", f"Marcar {len(lotes)} lote(s) para salida prioritaria?")
        if not confirm:
            return

        messagebox.showinfo("Salida prioritaria", f"Los lotes {', '.join(map(str, lotes))} fueron marcados para salida prioritaria.")
        self.lbl_estado.config(text=f"Salida prioritaria disparada para {len(lotes)} lote(s).")



if __name__ == '__main__':
    root = tb.Window(themename='litera')
    app = PanelLaurenteApp(root)
    root.mainloop()
