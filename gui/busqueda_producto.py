"""
Selector reutilizable: buscar producto escribiendo parte del nombre.
"""

import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *


class SelectorProductoPorNombre(tb.Frame):
    """
    Entry de búsqueda + listado filtrado. Expone get_codigo() / get_nombre()
    del producto seleccionado.
    """

    def __init__(self, master, on_select=None, altura_lista=5, **kwargs):
        super().__init__(master, **kwargs)
        self._productos = []  # [(codigo, nombre), ...]
        self._filtrados = []
        self._codigo = None
        self._nombre = None
        self._on_select = on_select

        fila_busqueda = tb.Frame(self)
        fila_busqueda.pack(fill=X)

        tb.Label(fila_busqueda, text="Buscar producto:", width=18).pack(side=LEFT)
        self.ent_busqueda = tb.Entry(fila_busqueda)
        self.ent_busqueda.pack(side=LEFT, fill=X, expand=YES, padx=(0, 8))
        self.ent_busqueda.bind("<KeyRelease>", self._filtrar)
        self.ent_busqueda.bind("<Return>", self._seleccionar_primero)

        self.lbl_seleccion = tb.Label(
            self,
            text="Ningún producto seleccionado",
            font=("Helvetica", 9, "italic"),
            bootstyle="secondary",
        )
        self.lbl_seleccion.pack(anchor=W, pady=(6, 4))

        lista_frame = tb.Frame(self)
        lista_frame.pack(fill=BOTH, expand=YES)

        self.lista = tk.Listbox(
            lista_frame,
            height=altura_lista,
            activestyle="dotbox",
            exportselection=False,
            font=("Helvetica", 10),
        )
        scroll = tb.Scrollbar(lista_frame, orient=VERTICAL, command=self.lista.yview)
        self.lista.configure(yscrollcommand=scroll.set)
        self.lista.pack(side=LEFT, fill=BOTH, expand=YES)
        scroll.pack(side=RIGHT, fill=Y)
        self.lista.bind("<<ListboxSelect>>", self._al_seleccionar)
        self.lista.bind("<Double-Button-1>", self._al_seleccionar)

    def set_productos(self, productos):
        """productos: iterable de (codigo, nombre)."""
        self._productos = list(productos)
        self._filtrados = list(self._productos)
        self._refrescar_lista()
        if not self._codigo:
            self.lbl_seleccion.config(
                text=f"{len(self._productos)} productos disponibles. Escribe para buscar.",
                bootstyle="secondary",
            )

    def get_codigo(self):
        return self._codigo

    def get_nombre(self):
        return self._nombre

    def limpiar(self):
        self._codigo = None
        self._nombre = None
        self.ent_busqueda.delete(0, END)
        self._filtrados = list(self._productos)
        self._refrescar_lista()
        self.lbl_seleccion.config(
            text="Ningún producto seleccionado",
            bootstyle="secondary",
        )

    def _filtrar(self, _event=None):
        termino = self.ent_busqueda.get().strip().lower()
        if not termino:
            self._filtrados = list(self._productos)
        else:
            self._filtrados = [
                (codigo, nombre)
                for codigo, nombre in self._productos
                if termino in str(nombre).lower() or termino in str(codigo).lower()
            ]
        self._refrescar_lista()

    def _refrescar_lista(self):
        self.lista.delete(0, END)
        limite = 80
        for codigo, nombre in self._filtrados[:limite]:
            self.lista.insert(END, f"{codigo} — {nombre}")
        if len(self._filtrados) > limite:
            self.lista.insert(END, f"... y {len(self._filtrados) - limite} más (refina la búsqueda)")

    def _al_seleccionar(self, _event=None):
        seleccion = self.lista.curselection()
        if not seleccion:
            return
        idx = seleccion[0]
        if idx >= len(self._filtrados[:80]):
            return
        codigo, nombre = self._filtrados[idx]
        self._codigo = codigo
        self._nombre = nombre
        self.lbl_seleccion.config(
            text=f"Seleccionado: {codigo} — {nombre}",
            bootstyle="success",
        )
        if self._on_select:
            self._on_select(codigo, nombre)

    def _seleccionar_primero(self, _event=None):
        if not self._filtrados:
            return
        self.lista.selection_clear(0, END)
        self.lista.selection_set(0)
        self.lista.activate(0)
        self._al_seleccionar()
