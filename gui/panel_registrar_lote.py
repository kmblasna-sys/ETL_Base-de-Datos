"""
Panel para registrar un lote recién comprado en Mineria_BD.
Inserta Lotes_de_Inventario, Compra y Detalle_Compra en el orden de FKs.
"""

import os
import sys
from datetime import date, datetime
from tkinter import messagebox

import ttkbootstrap as tb
from ttkbootstrap.constants import *

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "Conexion"))

from Conexion.conexion import obtener_conexion
from busqueda_producto import SelectorProductoPorNombre


class PanelRegistrarLote(tb.Frame):
    """Formulario de ingreso de lote comprado (lote + compra + detalle)."""

    def __init__(self, master, **kwargs):
        super().__init__(master, padding=15, **kwargs)
        self._almacenes = []
        self.crear_layout()
        self.cargar_catalogos()

    def crear_layout(self):
        header = tb.Frame(self)
        header.pack(fill=X, pady=(0, 10))

        tb.Label(
            header,
            text="Registrar Lote Comprado",
            font=("Helvetica", 14, "bold"),
            bootstyle="info",
        ).pack(anchor=W)
        tb.Label(
            header,
            text="Ingresa un lote recién adquirido: inventario, compra y detalle asociados.",
            font=("Helvetica", 10),
            bootstyle="secondary",
        ).pack(anchor=W, pady=(2, 0))

        tb.Separator(self, bootstyle="secondary").pack(fill=X, pady=(0, 15))

        form = tb.Labelframe(self, text="Datos del lote y compra", bootstyle="info", padding=20)
        form.pack(fill=X)

        fila1 = tb.Frame(form)
        fila1.pack(fill=X, pady=6)
        tb.Label(fila1, text="Número de lote:", width=22).pack(side=LEFT)
        self.ent_lote = tb.Entry(fila1, width=36)
        self.ent_lote.pack(side=LEFT, padx=(0, 10))
        tb.Button(
            fila1,
            text="Sugerir código",
            bootstyle="info-outline",
            command=self.sugerir_numero_lote,
        ).pack(side=LEFT)

        fila2 = tb.Frame(form)
        fila2.pack(fill=X, pady=6)
        tb.Label(fila2, text="Almacén:", width=22).pack(side=LEFT)
        self.combo_almacen = tb.Combobox(fila2, width=50, state="readonly")
        self.combo_almacen.pack(side=LEFT, fill=X, expand=YES)
        self.combo_almacen.bind("<<ComboboxSelected>>", lambda _e: self.sugerir_numero_lote())

        producto_box = tb.Labelframe(form, text="Producto", bootstyle="secondary", padding=10)
        producto_box.pack(fill=X, pady=(8, 6))
        self.selector_producto = SelectorProductoPorNombre(
            producto_box,
            altura_lista=5,
            on_select=lambda *_: self.sugerir_numero_lote(),
        )
        self.selector_producto.pack(fill=X)

        fila4 = tb.Frame(form)
        fila4.pack(fill=X, pady=6)
        tb.Label(fila4, text="Fecha ingreso/compra:", width=22).pack(side=LEFT)
        self.ent_fecha = tb.Entry(fila4, width=18)
        self.ent_fecha.insert(0, date.today().isoformat())
        self.ent_fecha.pack(side=LEFT, padx=(0, 20))
        tb.Label(fila4, text="YYYY-MM-DD", bootstyle="secondary").pack(side=LEFT)

        fila5 = tb.Frame(form)
        fila5.pack(fill=X, pady=6)
        tb.Label(fila5, text="Cantidad:", width=22).pack(side=LEFT)
        self.ent_cantidad = tb.Entry(fila5, width=14)
        self.ent_cantidad.insert(0, "1")
        self.ent_cantidad.pack(side=LEFT, padx=(0, 20))

        tb.Label(fila5, text="Espacio ocupado:", width=16).pack(side=LEFT)
        self.ent_espacio = tb.Entry(fila5, width=14)
        self.ent_espacio.insert(0, "0.00")
        self.ent_espacio.pack(side=LEFT, padx=(0, 20))

        tb.Label(fila5, text="Precio compra:", width=14).pack(side=LEFT)
        self.ent_precio = tb.Entry(fila5, width=14)
        self.ent_precio.pack(side=LEFT)

        acciones = tb.Frame(form)
        acciones.pack(fill=X, pady=(18, 0))
        tb.Button(
            acciones,
            text="Registrar lote comprado",
            bootstyle="success",
            padding=(14, 8),
            command=self.registrar_lote,
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
            text="Recargar catálogos",
            bootstyle="info-outline",
            padding=(14, 8),
            command=self.cargar_catalogos,
        ).pack(side=LEFT, padx=(10, 0))

        self.lbl_estado = tb.Label(
            self,
            text="Busca el producto por nombre, completa los datos y registra el lote.",
            font=("Helvetica", 10),
            bootstyle="secondary",
        )
        self.lbl_estado.pack(anchor=W, pady=(12, 0))

        historial = tb.Labelframe(
            self, text="Últimos lotes / compras registradas", bootstyle="secondary", padding=12
        )
        historial.pack(fill=BOTH, expand=YES, pady=(15, 0))

        columnas = ("lote", "almacen", "producto", "cantidad", "compra", "precio", "fecha")
        self.tree = tb.Treeview(
            historial, columns=columnas, show="headings", bootstyle="info", height=8
        )
        headers = {
            "lote": ("Número lote", 220),
            "almacen": ("Almacén", 100),
            "producto": ("Producto", 110),
            "cantidad": ("Cant.", 70),
            "compra": ("Id Compra", 90),
            "precio": ("Precio compra", 110),
            "fecha": ("Fecha", 110),
        }
        for col, (texto, ancho) in headers.items():
            self.tree.heading(col, text=texto, anchor=W)
            self.tree.column(col, width=ancho, anchor=CENTER if col in ("cantidad", "compra") else W)

        scroll_y = tb.Scrollbar(historial, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=YES)
        scroll_y.pack(side=RIGHT, fill=Y)

        self.cargar_historial()

    def cargar_catalogos(self):
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
            self.selector_producto.set_productos(cursor.fetchall())

            cursor.execute(
                "SELECT Codigo_Almacen, Nombre FROM Almacen ORDER BY Codigo_Almacen"
            )
            self._almacenes = cursor.fetchall()
            self.combo_almacen["values"] = [
                f"{codigo} — {nombre}" for codigo, nombre in self._almacenes
            ]
            if self.combo_almacen["values"]:
                self.combo_almacen.current(0)

            self.sugerir_numero_lote()
            self.lbl_estado.config(
                text="Catálogos cargados. Busca el producto por nombre.",
                bootstyle="secondary",
            )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron cargar los catálogos:\n{e}")
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
                SELECT l.Numero_Lote, l.Codigo_de_Almacen, dc.Codigo_de_Producto,
                       dc.Cantidad, c.Id_Compra, c.Precio_Compra, l.Fecha_ingreso
                FROM Lotes_de_Inventario l
                JOIN Detalle_Compra dc ON l.Numero_Lote = dc.Numero_Lote
                JOIN Compra c ON dc.Id_Compra = c.Id_Compra
                ORDER BY c.Id_Compra DESC, l.Fecha_ingreso DESC
                LIMIT 15
                """
            )
            for lote, almacen, producto, cantidad, id_compra, precio, fecha in cursor.fetchall():
                fecha_txt = (
                    fecha.strftime("%Y-%m-%d") if hasattr(fecha, "strftime") else str(fecha)
                )
                self.tree.insert(
                    "",
                    END,
                    values=(
                        lote,
                        almacen,
                        producto,
                        cantidad,
                        id_compra,
                        f"{float(precio):.2f}",
                        fecha_txt,
                    ),
                )
        except Exception as e:
            self.lbl_estado.config(
                text=f"No se pudo cargar el historial: {e}", bootstyle="danger"
            )
        finally:
            cursor.close()
            conn.close()

    def _codigo_almacen(self):
        valor = self.combo_almacen.get().strip()
        if not valor or "—" not in valor:
            return None
        return valor.split("—", 1)[0].strip()

    def sugerir_numero_lote(self):
        producto = self.selector_producto.get_codigo()
        almacen = self._codigo_almacen()
        fecha_raw = self.ent_fecha.get().strip()
        if not producto or not almacen:
            return

        try:
            fecha = datetime.strptime(fecha_raw, "%Y-%m-%d").date()
            ym = fecha.strftime("%Y%m")
        except ValueError:
            ym = date.today().strftime("%Y%m")

        sugerido = f"LOT-{producto}-{almacen}-{ym}"
        self.ent_lote.delete(0, END)
        self.ent_lote.insert(0, sugerido)

    def limpiar_formulario(self):
        self.ent_fecha.delete(0, END)
        self.ent_fecha.insert(0, date.today().isoformat())
        self.ent_cantidad.delete(0, END)
        self.ent_cantidad.insert(0, "1")
        self.ent_espacio.delete(0, END)
        self.ent_espacio.insert(0, "0.00")
        self.ent_precio.delete(0, END)
        self.selector_producto.limpiar()
        if self.combo_almacen["values"]:
            self.combo_almacen.current(0)
        self.sugerir_numero_lote()
        self.lbl_estado.config(text="Formulario listo.", bootstyle="secondary")

    def registrar_lote(self):
        numero_lote = self.ent_lote.get().strip()
        codigo_producto = self.selector_producto.get_codigo()
        codigo_almacen = self._codigo_almacen()
        fecha_raw = self.ent_fecha.get().strip()
        cantidad_raw = self.ent_cantidad.get().strip()
        espacio_raw = self.ent_espacio.get().strip().replace(",", ".")
        precio_raw = self.ent_precio.get().strip().replace(",", ".")

        if not numero_lote:
            messagebox.showwarning("Validación", "Ingresa el número de lote.")
            return
        if not codigo_producto:
            messagebox.showwarning(
                "Validación",
                "Busca el producto por nombre y selecciónalo de la lista.",
            )
            return
        if not codigo_almacen:
            messagebox.showwarning("Validación", "Selecciona un almacén.")
            return
        if not precio_raw:
            messagebox.showwarning("Validación", "Ingresa el precio de compra.")
            return

        try:
            fecha_ingreso = datetime.strptime(fecha_raw, "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror("Validación", "Fecha inválida. Usa YYYY-MM-DD.")
            return

        try:
            cantidad = int(cantidad_raw)
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Validación", "La cantidad debe ser un entero mayor a 0.")
            return

        try:
            espacio = float(espacio_raw)
            if espacio < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Validación", "El espacio ocupado debe ser un número válido.")
            return

        try:
            precio = float(precio_raw)
            if precio < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Validación", "El precio de compra debe ser un número válido.")
            return

        conn = obtener_conexion()
        if not conn:
            messagebox.showerror("Conexión", "No hay conexión con Mineria_BD.")
            return

        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT 1 FROM Lotes_de_Inventario WHERE Numero_Lote = %s",
                (numero_lote,),
            )
            if cursor.fetchone():
                messagebox.showerror(
                    "Lote duplicado",
                    f"Ya existe el lote '{numero_lote}'. Cambia el número o usa 'Sugerir código'.",
                )
                return

            cursor.execute(
                """
                INSERT INTO Lotes_de_Inventario
                    (Numero_Lote, Codigo_de_Almacen, Fecha_ingreso, Espacio_ocupado)
                VALUES (%s, %s, %s, %s)
                """,
                (numero_lote, codigo_almacen, fecha_ingreso, espacio),
            )

            cursor.execute(
                """
                INSERT INTO Compra (Fecha_Compra, Precio_Compra)
                VALUES (%s, %s)
                """,
                (fecha_ingreso, precio),
            )
            id_compra = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO Detalle_Compra
                    (Id_Compra, Numero_Lote, Codigo_de_Producto, Cantidad)
                VALUES (%s, %s, %s, %s)
                """,
                (id_compra, numero_lote, codigo_producto, cantidad),
            )

            conn.commit()
            self.lbl_estado.config(
                text=(
                    f"Lote '{numero_lote}' registrado. "
                    f"Compra #{id_compra} — {codigo_producto} x{cantidad}."
                ),
                bootstyle="success",
            )
            messagebox.showinfo(
                "Éxito",
                (
                    f"Lote comprado registrado correctamente.\n"
                    f"Lote: {numero_lote}\nId Compra: {id_compra}"
                ),
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
    root.title("Prueba - Registrar Lote Comprado")
    root.geometry("1100x800")
    PanelRegistrarLote(root).pack(fill=BOTH, expand=YES)
    root.mainloop()
