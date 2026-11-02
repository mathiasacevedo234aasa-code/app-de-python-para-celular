"""tkinter.messagebox sobre Kivy."""
from tkinter import _dialog

ERROR, INFO, QUESTION, WARNING = "error", "info", "question", "warning"
ABORTRETRYIGNORE, OK, OKCANCEL, RETRYCANCEL, YESNO, YESNOCANCEL = (
    "abortretryignore", "ok", "okcancel", "retrycancel", "yesno", "yesnocancel")
ABORT, RETRY, IGNORE, CANCEL, YES, NO = "abort", "retry", "ignore", "cancel", "yes", "no"


def showinfo(title=None, message=None, **options):
    _dialog(title or "Información", message, [("Aceptar", "ok")])
    return "ok"


def showwarning(title=None, message=None, **options):
    _dialog(title or "Advertencia", message, [("Aceptar", "ok")])
    return "ok"


def showerror(title=None, message=None, **options):
    _dialog(title or "Error", message, [("Aceptar", "ok")])
    return "ok"


def askquestion(title=None, message=None, **options):
    return _dialog(title or "Pregunta", message, [("No", "no"), ("Sí", "yes")]) or "no"


def askyesno(title=None, message=None, **options):
    return _dialog(title or "Pregunta", message, [("No", False), ("Sí", True)]) is True


def askokcancel(title=None, message=None, **options):
    return _dialog(title or "Confirmar", message, [("Cancelar", False), ("Aceptar", True)]) is True


def askretrycancel(title=None, message=None, **options):
    return _dialog(title or "Reintentar", message, [("Cancelar", False), ("Reintentar", True)]) is True


def askyesnocancel(title=None, message=None, **options):
    r = _dialog(title or "Pregunta", message, [("Cancelar", "c"), ("No", False), ("Sí", True)])
    return None if r == "c" else r


class Message:
    def __init__(self, master=None, **options):
        self.options = options

    def show(self, **options):
        o = dict(self.options, **options)
        return showinfo(o.get("title"), o.get("message"))
