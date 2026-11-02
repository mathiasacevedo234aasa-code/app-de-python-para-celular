"""tkinter.filedialog: elige archivos dentro de la carpeta de proyectos."""
import os
import threading

from tkinter import _check_stop, _is_main, _ui


def _projects_dir():
    return os.getcwd()


def _choose(title, save=False, initialfile="", directory=False, filetypes=None):
    from kivy.metrics import dp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.filechooser import FileChooserListView
    from kivy.uix.popup import Popup
    from kivy.uix.textinput import TextInput

    box = {}
    done = threading.Event()

    def build():
        content = BoxLayout(orientation="vertical", spacing=dp(6))
        filters = []
        for ft in filetypes or ():
            pats = ft[1] if isinstance(ft[1], (list, tuple)) else str(ft[1]).split()
            filters += [p for p in pats if p not in ("*", "*.*")]
        chooser = FileChooserListView(path=_projects_dir(), dirselect=directory, filters=filters)
        content.add_widget(chooser)
        name = None
        if save:
            name = TextInput(text=initialfile or "", multiline=False, size_hint_y=None, height=dp(44),
                             hint_text="Nombre del archivo")
            content.add_widget(name)
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        popup = Popup(title=title, content=content, size_hint=(0.95, 0.9), auto_dismiss=False)

        def finish(value):
            box["v"] = value
            popup.dismiss()
            done.set()

        def ok(*a):
            if save:
                if name.text.strip():
                    finish(os.path.join(chooser.path, name.text.strip()))
            elif directory:
                finish(chooser.selection[0] if chooser.selection else chooser.path)
            elif chooser.selection:
                finish(chooser.selection[0])

        cancel = Button(text="Cancelar")
        cancel.bind(on_release=lambda *a: finish(""))
        accept = Button(text="Guardar" if save else "Abrir", background_normal="",
                        background_color=(0.04, 0.39, 0.68, 1))
        accept.bind(on_release=ok)
        row.add_widget(cancel)
        row.add_widget(accept)
        content.add_widget(row)
        if save:
            chooser.bind(selection=lambda w, s: s and setattr(name, "text", os.path.basename(s[0])))
        popup.open()

    if _is_main():
        build()
        return ""
    _ui(build)
    while not done.wait(0.05):
        _check_stop()
    return box.get("v", "")


def askopenfilename(**options):
    return _choose(options.get("title", "Abrir"), filetypes=options.get("filetypes"))


def askopenfilenames(**options):
    r = askopenfilename(**options)
    return (r,) if r else ()


def asksaveasfilename(**options):
    r = _choose(options.get("title", "Guardar como"), save=True, initialfile=options.get("initialfile", ""),
                filetypes=options.get("filetypes"))
    ext = options.get("defaultextension", "")
    if r and ext and not os.path.splitext(r)[1]:
        r += ext
    return r


def askdirectory(**options):
    return _choose(options.get("title", "Elegir carpeta"), directory=True)


def askopenfile(mode="r", **options):
    fn = askopenfilename(**options)
    return open(fn, mode, encoding=None if "b" in mode else "utf-8") if fn else None


def asksaveasfile(mode="w", **options):
    fn = asksaveasfilename(**options)
    return open(fn, mode, encoding=None if "b" in mode else "utf-8") if fn else None
