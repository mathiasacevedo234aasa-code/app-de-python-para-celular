# PyStudio Móvil

IDE de Python para Android con soporte de **tkinter**, hecho con Kivy.

## Funciones
- Editor con resaltado de sintaxis, números de línea, sangría automática y pestañas.
- Tema oscuro y claro (menú `...` → Tema).
- Consola con `print()` e `input()`; botón Ejecutar/Detener.
- Al haber un error, salta a la línea que falló.
- Barra de teclas rápidas para símbolos de programación.
- Capa compatible de **tkinter** (`compat/tkinter`): Tk, Toplevel, Frame, LabelFrame, Label,
  Button, Entry, Text, Checkbutton, Radiobutton, Listbox, Scale, Spinbox, Canvas,
  pack/grid/place, variables, `after`, `bind`, `messagebox`, `simpledialog`, `filedialog`
  y `ttk` (Combobox, Progressbar, Notebook, Treeview…).
- Ejemplos incluidos (menú `...` → Ejemplos).

> Limitaciones: no es Tk real. Los menús de escritorio, las imágenes avanzadas y algunos
> detalles de `ttk.Style` se aceptan, pero no se dibujan. Solo puedes usar las librerías
> que estén en `requirements` del `buildozer.spec`; no se puede usar `pip` dentro de la app.

## Compilar la APK (sin instalar nada: GitHub Actions)
1. Crea un repositorio en GitHub y sube todos estos archivos (incluida la carpeta `.github`).
2. Ve a la pestaña **Actions**, abre el workflow **Compilar APK** y pulsa **Run workflow**.
3. Al terminar (unos 20–40 min la primera vez), descarga el artefacto **PyStudio-apk**.
4. Copia el `.apk` al celular e instálalo (permite "instalar apps de origen desconocido").

## Compilar en tu PC (Linux o WSL en Windows)
```bash
pip install buildozer "cython<3.0"
buildozer -v android debug
```
La APK queda en `bin/`.

## Probar en el escritorio
```bash
pip install "kivy[base]==2.3.1" pygments
python main.py
```
