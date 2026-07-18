"""
Panel para registrar una venta en Mineria_BD.
Inserta en Venta y DetalleVenta respetando las FK del esquema.
"""

import os
import sys
from datetime import datetime
from tkinter import messagebox

import ttkbootstrap as tb
from ttkbootstrap.constants import *

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "Conexion"))

from Conexion.conexion import obtener_conexion
from busqueda_producto import SelectorProductoPorNombre


class PanelRegistrarVenta(tb.Frame):
    """Formulario de registro de ventas (Venta + DetalleVenta)."""

    def __init__(self, master, **kwargs):
        super().__init__(master, padding=15, **kwargs)
        self.crear_layout()
        self.cargar_productos()

    def crear_layout(self):
        header = tb.Frame(self)
        header.pack(fill=X, pady=(0, 10))

        tb.Label(
            header,
            text="Registrar Venta",
            font=("Helvetica", 14, "bold"),
            bootstyle="primary",
        ).pack(anchor=W)
        tb.Label(
            header,
            text="Registra una transacción de venta y su detalle de producto en Mineria_BD.",
            font=("Helvetica", 10),
            bootstyle="secondary",
        ).pack(anchor=W, pady=(2, 0))

        tb.Separator(self, bootstyle="secondary").pack(fill=X, pady=(0, 15))

        form = tb.Labelframe(self, text="Datos de la venta", bootstyle="primary", padding=20)
        form.pack(fill=X)

        fila1 = tb.Frame(form)
        fila1.pack(fill=X, pady=6)
        tb.Label(fila1, text="Fecha/Hora emisión:", width=22).pack(side=LEFT)
        self.ent_fecha = tb.Entry(fila1, width=28)
        self.ent_fecha.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.ent_fecha.pack(side=LEFT, padx=(0, 20))
        tb.Label(fila1, text="Formato: YYYY-MM-DD HH:MM:SS", bootstyle="secondary").pack(side=LEFT)

        producto_box = tb.Labelframe(form, text="Producto", bootstyle="secondary", padding=10)
        producto_box.pack(fill=X, pady=(8, 6))
        self.selector_producto = SelectorProductoPorNombre(producto_box, altura_lista=6)
        self.selector_producto.pack(fill=X)

        fila3 = tb.Frame(form)
        fila3.pack(fill=X, pady=6)
        tb.Label(fila3, text="Cantidad adquirida:", width=22).pack(side=LEFT)
        self.ent_cantidad = tb.Entry(fila3, width=16)
        self.ent_cantidad.insert(0, "1")
        self.ent_cantidad.pack(side=LEFT, padx=(0, 20))

        tb.Label(fila3, text="Precio venta (total):", width=18).pack(side=LEFT)
        self.ent_precio = tb.Entry(fila3, width=16)
        self.ent_precio.pack(side=LEFT)

        acciones = tb.Frame(form)
        acciones.pack(fill=X, pady=(18, 0))
        tb.Button(
            acciones,
            text="Registrar venta",
            bootstyle="success",
            padding=(14, 8),
            command=self.registrar_venta,
        ).pack(side=LEFT)
        tb.Button(
            acciones,
            text="Limpiar",
            bootstyle="secondary-outline",
            padding=(14, 8),
            command=self.limpiar_formulario,
        ).pack(side=LEFT, padx=(10, 0))
        tb.Button(
            acciones,
            text="Recargar productos",
            bootstyle="info-outline",
            padding=(14, 8),
            command=self.cargar_productos,
        ).pack(side=LEFT, padx=(10, 0))

        self.lbl_estado = tb.Label(
            self,
            text="Escribe el nombre del producto, selecciónalo y registra la venta.",
            font=("Helvetica", 10),
            bootstyle="secondary",
        )
        self.lbl_estado.pack(anchor=W, pady=(12, 0))

        historial = tb.Labelframe(
            self, text="Últimas ventas registradas", bootstyle="secondary", padding=12
        )
        historial.pack(fill=BOTH, expand=YES, pady=(15, 0))

        columnas = ("transaccion", "fecha", "precio", "producto", "cantidad")
        self.tree = tb.Treeview(
            historial, columns=columnas, show="headings", bootstyle="primary", height=8
        )
        headers = {
            "transaccion": ("N° Transacción", 120),
            "fecha": ("Fecha / Hora", 170),
            "precio": ("Precio venta", 110),
            "producto": ("Producto", 380),
            "cantidad": ("Cantidad", 90),
        }
        for col, (texto, ancho) in headers.items():
            self.tree.heading(col, text=texto, anchor=W)
            self.tree.column(col, width=ancho, anchor=W if col != "cantidad" else CENTER)

        scroll_y = tb.Scrollbar(historial, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)
        scroll_y.pack(side=RIGHT, fill=Y)

        self.cargar_historial()

    def cargar_productos(self):
        conn = obtener_conexion()
        if not conn:
            self.lbl_estado.config(
                text="Sin conexión a la base de datos.", bootstyle="danger"
            )
            return

        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT Codigo_de_Producto, Nombre FROM Producto ORDER BY Nombre"
            )
            productos = cursor.fetchall()
            self.selector_producto.set_productos(productos)
            self.lbl_estado.config(
                text=f"{len(productos)} productos cargados. Busca por nombre.",
                bootstyle="secondary",
            )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron cargar los productos:\n{e}")
        finally:
            cursor.close()
            conn.close()

    def cargar_historial(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        conn = obtener_conexion()
        if not conn:
            return

        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT v.Numero_Transaccion, v.Fecha_Hora_Emision, v.Precio_venta,
                       dv.Codigo_de_Producto, dv.Cantidad_Adquirida
                FROM Venta v
                JOIN DetalleVenta dv ON v.Numero_Transaccion = dv.Numero_Transaccion
                ORDER BY v.Numero_Transaccion DESC
                LIMIT 15
                """
            )
            for nro, fecha, precio, producto, cantidad in cursor.fetchall():
                fecha_txt = (
                    fecha.strftime("%Y-%m-%d %H:%M:%S")
                    if hasattr(fecha, "strftime")
                    else str(fecha)
                )
                self.tree.insert(
                    "",
                    END,
                    values=(nro, fecha_txt, f"{float(precio):.2f}", producto, cantidad),
                )
        except Exception as e:
            self.lbl_estado.config(
                text=f"No se pudo cargar el historial: {e}", bootstyle="danger"
            )
        finally:
            cursor.close()
            conn.close()

    def limpiar_formulario(self):
        self.ent_fecha.delete(0, END)
        self.ent_fecha.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.ent_cantidad.delete(0, END)
        self.ent_cantidad.insert(0, "1")
        self.ent_precio.delete(0, END)
        self.selector_producto.limpiar()
        self.lbl_estado.config(text="Formulario listo.", bootstyle="secondary")

    def registrar_venta(self):
        codigo_producto = self.selector_producto.get_codigo()
        fecha_raw = self.ent_fecha.get().strip()
        cantidad_raw = self.ent_cantidad.get().strip()
        precio_raw = self.ent_precio.get().strip().replace(",", ".")

        if not codigo_producto:
            messagebox.showwarning(
                "Validación",
                "Busca el producto por nombre y selecciónalo de la lista.",
            )
            return
        if not precio_raw:
            messagebox.showwarning("Validación", "Ingresa el precio de venta.")
            return

        try:
            fecha_emision = datetime.strptime(fecha_raw, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                fecha_emision = datetime.strptime(fecha_raw, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror(
                    "Validación",
                    "Fecha inválida. Usa YYYY-MM-DD HH:MM:SS o YYYY-MM-DD.",
                )
                return

        try:
            cantidad = int(cantidad_raw)
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Validación", "La cantidad debe ser un entero mayor a 0.")
            return

        try:
            precio = float(precio_raw)
            if precio < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Validación", "El precio de venta debe ser un número válido.")
            return

        conn = obtener_conexion()
        if not conn:
            messagebox.showerror("Conexión", "No hay conexión con Mineria_BD.")
            return

        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO Venta (Fecha_Hora_Emision, Precio_venta)
                VALUES (%s, %s)
                """,
                (fecha_emision, precio),
            )
            numero_transaccion = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO DetalleVenta
                    (Numero_Transaccion, Codigo_de_Producto, Cantidad_Adquirida, Precio_Unitario, Utilidad)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (numero_transaccion, codigo_producto, cantidad, 10.2,10.2),
            )

            conn.commit()
            self.lbl_estado.config(
                text=(
                    f"Venta registrada. Transacción #{numero_transaccion} "
                    f"— {codigo_producto} x{cantidad}."
                ),
                bootstyle="success",
            )
            messagebox.showinfo(
                "Éxito",
                f"Venta registrada correctamente.\nN° Transacción: {numero_transaccion}",
            )
            self.limpiar_formulario()
            self.cargar_historial()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Error al registrar", str(e))
            self.lbl_estado.config(text=f"Error: {e}", bootstyle="danger")
        finally:
            cursor.close()
            conn.close()


if __name__ == "__main__":
    app_style = tb.Style(theme="flatly")
    root = app_style.master
    root.title("Prueba - Registrar Venta")
    root.geometry("1000x750")
    PanelRegistrarVenta(root).pack(fill=BOTH, expand=YES)
    root.mainloop()
