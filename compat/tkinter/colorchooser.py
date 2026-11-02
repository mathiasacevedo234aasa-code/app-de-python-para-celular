"""tkinter.colorchooser: paleta simple de colores."""
from tkinter import _dialog

_COLORS = [("Rojo", "#e53935"), ("Naranja", "#fb8c00"), ("Amarillo", "#fdd835"), ("Verde", "#43a047"),
           ("Azul", "#1e88e5"), ("Morado", "#8e24aa"), ("Negro", "#000000"), ("Blanco", "#ffffff")]


def askcolor(color=None, **options):
    c = _dialog(options.get("title", "Elegir color"), "", [(n, h) for n, h in _COLORS] + [("Cancelar", None)],
                vertical=True)
    if not c:
        return (None, None)
    return (tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)), c)
