"""tkinter.simpledialog sobre Kivy."""
from tkinter import _dialog
from tkinter import messagebox


def _ask(title, prompt, kind, initialvalue=None, minvalue=None, maxvalue=None):
    while True:
        r = _dialog(title, prompt, [("Cancelar", None), ("Aceptar", True)], entry=kind,
                    initial="" if initialvalue is None else initialvalue)
        if r is None:
            return None
        try:
            v = {"int": int, "float": float}.get(kind, str)(r)
        except ValueError:
            messagebox.showwarning("Valor no válido", "Escribe un número válido.")
            continue
        if minvalue is not None and v < minvalue or maxvalue is not None and v > maxvalue:
            messagebox.showwarning("Fuera de rango", "El valor debe estar entre %s y %s." % (minvalue, maxvalue))
            continue
        return v


def askstring(title, prompt, **kw):
    return _ask(title, prompt, "text", kw.get("initialvalue"))


def askinteger(title, prompt, **kw):
    return _ask(title, prompt, "int", kw.get("initialvalue"), kw.get("minvalue"), kw.get("maxvalue"))


def askfloat(title, prompt, **kw):
    return _ask(title, prompt, "float", kw.get("initialvalue"), kw.get("minvalue"), kw.get("maxvalue"))


class Dialog:
    def __init__(self, parent, title=None):
        self.result = None
        self.title = title
