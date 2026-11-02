"""PyStudio Móvil — IDE de Python para Android con soporte de tkinter."""
import os
import re
import sys
import time

APP_DIR = os.path.dirname(os.path.abspath(__file__))
# La capa compatible de tkinter vive en compat/tkinter y debe tener prioridad.
sys.path.insert(0, os.path.join(APP_DIR, "vendor"))  # librerías de Python puro empaquetadas
sys.path.insert(0, os.path.join(APP_DIR, "compat"))
sys.path.insert(0, APP_DIR)

from kivy.app import App
from kivy.cache import Cache
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, ListProperty, StringProperty
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.codeinput import CodeInput
from kivy.uix.dropdown import DropDown
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.stencilview import StencilView
from kivy.uix.textinput import TextInput
from kivy.utils import get_color_from_hex as hexc
from pygments.formatters import BBCodeFormatter
from pygments.lexers.python import PythonLexer

from examples import EXAMPLES
from runtime import Runner

THEMES = {
    "oscuro": {
        "bg": "#1e2228", "panel": "#22262d", "bar": "#282c34", "btn": "#353b45", "btn_down": "#454c59",
        "text": "#d7dae0", "muted": "#7f848e", "accent": "#61afef", "run": "#2ea043", "stop": "#e5534b",
        "gutter": "#1e2228", "console": "#191c21", "field": "#2c313a", "line": "#323842",
        "code_style": "one-dark", "on_accent": "#10141a",
    },
    "claro": {
        "bg": "#fbfbfc", "panel": "#f1f3f6", "bar": "#ffffff", "btn": "#e8ebef", "btn_down": "#d5d9e0",
        "text": "#24292f", "muted": "#8a919b", "accent": "#0969da", "run": "#1f883d", "stop": "#cf222e",
        "gutter": "#fbfbfc", "console": "#f6f8fa", "field": "#ffffff", "line": "#e1e4e8",
        "code_style": "default", "on_accent": "#ffffff",
    },
}
MONO = "RobotoMono-Regular"

KV = """
#:import hexc kivy.utils.get_color_from_hex
#:import Factory kivy.factory.Factory

<FlatButton>:
    background_normal: ''
    background_down: ''
    background_disabled_normal: ''
    background_color: 0, 0, 0, 0
    color: self.fg if self.fg else app.t_text
    font_size: '14sp'
    size_hint_x: None
    width: max(self.texture_size[0] + dp(20), dp(44))
    canvas.before:
        Color:
            rgba: (self.bg or app.t_btn) if self.state == 'normal' else (self.bg_down or app.t_btn_down)
        RoundedRectangle:
            pos: self.x + dp(2), self.y + dp(4)
            size: max(0, self.width - dp(4)), max(0, self.height - dp(8))
            radius: [dp(self.radius)]

<Divider@Widget>:
    size_hint_y: None
    height: dp(1)
    canvas:
        Color:
            rgba: app.t_line
        Rectangle:
            pos: self.pos
            size: self.size

<Root>:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: app.t_bg
        Rectangle:
            pos: self.pos
            size: self.size

    # ---------- barra superior ----------
    BoxLayout:
        size_hint_y: None
        height: dp(60)
        padding: dp(10), dp(6), dp(6), dp(6)
        spacing: dp(2)
        canvas.before:
            Color:
                rgba: app.t_bar
            Rectangle:
                pos: self.pos
                size: self.size
        Label:
            text: 'Py'
            bold: True
            font_size: '17sp'
            color: app.t_on_accent
            size_hint: None, None
            size: dp(38), dp(38)
            pos_hint: {'center_y': .5}
            canvas.before:
                Color:
                    rgba: app.t_accent
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(11)]
        Widget:
        FlatButton:
            text: 'Nuevo'
            bg: [0, 0, 0, 0]
            on_release: app.new_file()
        FlatButton:
            text: 'Abrir'
            bg: [0, 0, 0, 0]
            on_release: app.open_dialog()
        FlatButton:
            text: 'Guardar'
            bg: [0, 0, 0, 0]
            on_release: app.save_current()
        FlatButton:
            text: 'Detener' if app.running else 'Ejecutar'
            bg: app.t_stop if app.running else app.t_run
            bg_down: [c * 0.8 for c in self.bg[:3]] + [1]
            fg: [1, 1, 1, 1]
            bold: True
            radius: 20
            width: max(self.texture_size[0] + dp(28), dp(88))
            on_release: app.toggle_run()
        FlatButton:
            text: '...'
            bold: True
            bg: [0, 0, 0, 0]
            width: dp(44)
            on_release: app.open_menu(self)

    # ---------- pestañas ----------
    ScrollView:
        size_hint_y: None
        height: dp(42)
        do_scroll_y: False
        bar_width: 0
        canvas.before:
            Color:
                rgba: app.t_bar
            Rectangle:
                pos: self.pos
                size: self.size
        BoxLayout:
            id: tabs
            size_hint_x: None
            width: self.minimum_width
            padding: dp(6), 0
            spacing: dp(2)
    Divider:

    # ---------- editor + consola ----------
    BoxLayout:
        orientation: 'vertical'
        BoxLayout:
            id: editor_area
        Splitter:
            strip_cls: Factory.GripStrip
            strip_size: dp(14)
            sizable_from: 'top'
            size_hint_y: None
            height: dp(240)
            min_size: dp(100)
            max_size: dp(900)
            BoxLayout:
                orientation: 'vertical'
                canvas.before:
                    Color:
                        rgba: app.t_console
                    Rectangle:
                        pos: self.pos
                        size: self.size
                BoxLayout:
                    size_hint_y: None
                    height: dp(40)
                    padding: dp(14), 0, dp(6), 0
                    Label:
                        text: 'CONSOLA'
                        bold: True
                        font_size: '12sp'
                        color: app.t_muted
                        halign: 'left'
                        valign: 'middle'
                        text_size: self.size
                    FlatButton:
                        text: 'Limpiar'
                        font_size: '13sp'
                        bg: [0, 0, 0, 0]
                        fg: app.t_muted
                        on_release: app.clear_console()
                TextInput:
                    id: console
                    readonly: True
                    font_name: 'RobotoMono-Regular'
                    font_size: app.font_size * 0.9
                    line_spacing: dp(3)
                    padding: dp(14), dp(4)
                    background_normal: ''
                    background_active: ''
                    background_color: app.t_console
                    foreground_color: app.t_text
                    cursor_color: 0, 0, 0, 0
                    selection_color: app.t_accent[:3] + [0.3]
                BoxLayout:
                    size_hint_y: None
                    height: dp(56)
                    padding: dp(10), dp(6)
                    spacing: dp(6)
                    TextInput:
                        id: stdin
                        multiline: False
                        disabled: not app.waiting_input
                        hint_text: 'Escribe la respuesta y pulsa Enviar' if app.waiting_input else 'El programa no está pidiendo datos'
                        font_name: 'RobotoMono-Regular'
                        font_size: '15sp'
                        padding: dp(14), dp(12)
                        background_normal: ''
                        background_active: ''
                        background_disabled_normal: ''
                        background_color: 0, 0, 0, 0
                        foreground_color: app.t_text
                        disabled_foreground_color: app.t_muted
                        hint_text_color: app.t_muted
                        cursor_color: app.t_accent
                        cursor_width: dp(2)
                        on_text_validate: app.send_input()
                        canvas.before:
                            Color:
                                rgba: app.t_field
                            RoundedRectangle:
                                pos: self.pos
                                size: self.size
                                radius: [dp(12)]
                            Color:
                                rgba: app.t_accent if app.waiting_input else app.t_line
                            Line:
                                rounded_rectangle: self.x, self.y, self.width, self.height, dp(12)
                                width: dp(1.3)
                    FlatButton:
                        text: 'Enviar'
                        disabled: not app.waiting_input
                        bg: app.t_accent if app.waiting_input else app.t_btn
                        fg: app.t_on_accent if app.waiting_input else app.t_muted
                        radius: 12
                        on_release: app.send_input()

    # ---------- teclas rápidas ----------
    Divider:
    ScrollView:
        size_hint_y: None
        height: dp(50)
        do_scroll_y: False
        bar_width: 0
        canvas.before:
            Color:
                rgba: app.t_bar
            Rectangle:
                pos: self.pos
                size: self.size
        BoxLayout:
            id: keybar
            size_hint_x: None
            width: self.minimum_width
            padding: dp(4), dp(2)
            spacing: dp(2)

    # ---------- barra de estado ----------
    BoxLayout:
        size_hint_y: None
        height: dp(28)
        padding: dp(12), 0
        spacing: dp(8)
        canvas.before:
            Color:
                rgba: app.t_bar
            Rectangle:
                pos: self.pos
                size: self.size
        Widget:
            size_hint: None, None
            size: dp(8), dp(8)
            pos_hint: {'center_y': .5}
            canvas:
                Color:
                    rgba: app.status_color
                Ellipse:
                    pos: self.pos
                    size: self.size
        Label:
            text: app.status
            font_size: '12sp'
            color: app.t_text
            text_size: self.size
            halign: 'left'
            valign: 'middle'
            shorten: True
        Label:
            text: app.cursor_pos
            font_size: '12sp'
            color: app.t_muted
            size_hint_x: None
            width: dp(110)
            text_size: self.size
            halign: 'right'
            valign: 'middle'

<GripStrip@SplitterStrip>:
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    canvas.after:
        Color:
            rgba: app.t_line
        Rectangle:
            pos: self.x, self.center_y
            size: self.width, dp(1)
        Color:
            rgba: app.t_muted
        RoundedRectangle:
            pos: self.center_x - dp(20), self.center_y - dp(2)
            size: dp(40), dp(4)
            radius: [dp(2)]
"""


class FlatButton(Button):
    bg = ListProperty([])
    bg_down = ListProperty([])
    fg = ListProperty([])
    radius = 10


class Root(BoxLayout):
    pass


class Editor(CodeInput):
    """CodeInput con sangría automática y tabulación a 4 espacios."""

    def insert_text(self, substring, from_undo=False):
        if not from_undo:
            if substring == "\t":
                substring = "    "
            elif substring == "\n":
                line = self._lines[self.cursor_row][: self.cursor_col]
                indent = len(line) - len(line.lstrip(" "))
                if line.rstrip().endswith(":"):
                    indent += 4
                substring = "\n" + " " * indent
        return super().insert_text(substring, from_undo=from_undo)

    def keyboard_on_key_down(self, window, keycode, text, modifiers):
        # Retroceso sobre sangría: borra 4 espacios de una vez
        if keycode[1] == "backspace" and not self.selection_text:
            line = self._lines[self.cursor_row][: self.cursor_col]
            if line and not line.strip(" ") and len(line) % 4 == 0:
                for _ in range(3):
                    self.do_backspace()
        return super().keyboard_on_key_down(window, keycode, text, modifiers)


class Gutter(StencilView):
    """Números de línea sincronizados con el desplazamiento del editor."""

    def __init__(self, editor, app, **kw):
        super().__init__(**kw)
        self.editor = editor
        self.app = app
        self.size_hint_x = None
        self._cache = {}
        for prop in ("scroll_y", "text", "size", "pos", "cursor", "font_size"):
            editor.bind(**{prop: self._schedule})
        self.bind(size=self._schedule, pos=self._schedule)
        app.bind(t_gutter=self._retheme)
        self._ev = None

    def _retheme(self, *_):
        self._cache.clear()
        self._schedule()

    def _schedule(self, *_):
        if self._ev is None:
            self._ev = Clock.schedule_once(self.draw, 0)

    def _tex(self, n, current):
        key = (n, current, self.editor.font_size)
        tex = self._cache.get(key)
        if tex is None:
            if len(self._cache) > 600:
                self._cache.clear()
            lbl = CoreLabel(text=str(n), font_size=self.editor.font_size * 0.82, font_name=MONO,
                            color=self.app.t_text if current else self.app.t_muted)
            lbl.refresh()
            tex = self._cache[key] = lbl.texture
        return tex

    def draw(self, *_):
        self._ev = None
        ed = self.editor
        nlines = len(ed._lines)
        self.width = dp(22) + len(str(nlines)) * ed.font_size * 0.55
        lh = ed.line_height + ed.line_spacing
        self.canvas.clear()
        with self.canvas:
            Color(*self.app.t_gutter)
            Rectangle(pos=self.pos, size=self.size)
            if lh <= 0:
                return
            first = max(0, int(ed.scroll_y // lh))
            last = min(nlines, first + int(ed.height // lh) + 2)
            for row in range(first, last):
                y = ed.top - ed.padding[1] + ed.scroll_y - (row + 1) * lh
                tex = self._tex(row + 1, row == ed.cursor_row)
                Color(1, 1, 1, 1)
                Rectangle(texture=tex, size=tex.size,
                          pos=(self.right - tex.width - dp(10), y + (lh - tex.height) / 2))


class Document:
    def __init__(self, app, path, text=""):
        self.app = app
        self.path = path
        self.dirty = False
        self.editor = Editor(
            lexer=PythonLexer(), font_name=MONO, font_size=app.font_size,
            do_wrap=False, unfocus_on_touch=False, auto_indent=False,
            background_normal="", background_active="", line_spacing=dp(4),
            padding=(dp(6), dp(10), dp(10), dp(10)), cursor_width=dp(2),
        )
        self.editor.keyboard_suggestions = False
        self.apply_theme()
        # El texto se asigna después de do_wrap/estilo para que las líneas no queden cortadas
        self.editor.text = text
        self.editor.bind(text=self._changed, cursor=app.update_cursor_pos)
        self.view = BoxLayout()
        self.view.add_widget(Gutter(self.editor, app))
        self.view.add_widget(self.editor)

    def apply_theme(self):
        app, ed = self.app, self.editor
        try:
            ed.style_name = app.theme["code_style"]
        except Exception:
            ed.style_name = "monokai"
        ed.formatter = BBCodeFormatter(style=ed.style_name)
        Cache.remove("textinput.label")  # las líneas se cachean por texto, no por estilo
        ed.background_color = app.t_bg
        ed.cursor_color = app.t_accent
        ed.selection_color = app.t_accent[:3] + [0.28]
        if ed.text:
            # Recolorear: CodeInput no vuelve a formatear el texto al cambiar de estilo
            dirty, cursor, text = self.dirty, ed.cursor, ed.text
            ed.text = ""
            ed.text = text
            ed.cursor = cursor
            self.dirty = dirty
            app.refresh_tabs()

    @property
    def name(self):
        return os.path.basename(self.path)

    def _changed(self, *_):
        if not self.dirty:
            self.dirty = True
            self.app.refresh_tabs()

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(self.editor.text)
        self.dirty = False
        self.app.refresh_tabs()


KEYS = [("Tab", "    "), ("(", "("), (")", ")"), (":", ":"), ('"', '"'), ("'", "'"),
        ("[", "["), ("]", "]"), ("{", "{"), ("}", "}"), ("=", "="), ("+", "+"), ("-", "-"),
        ("*", "*"), ("/", "/"), ("#", "#"), ("_", "_"), (".", "."), (",", ","), ("<", "<"),
        (">", ">"), ("!", "!"), ("%", "%"), ("Izq", "@left"), ("Der", "@right"),
        ("Arriba", "@up"), ("Abajo", "@down"), ("Deshacer", "@undo"), ("Rehacer", "@redo")]


def _theme_props():
    return {"t_" + k: ListProperty(hexc(v)) for k, v in THEMES["oscuro"].items() if k.startswith(("#",)) is False
            and isinstance(v, str) and v.startswith("#")}


class PyStudioApp(App):
    title = "PyStudio"
    running = BooleanProperty(False)
    waiting_input = BooleanProperty(False)
    status = StringProperty("Listo")
    status_color = ListProperty(hexc("#61afef"))
    cursor_pos = StringProperty("Ln 1, Col 1")
    font_size = sp(15)
    theme_name = "oscuro"
    locals().update(_theme_props())

    @property
    def theme(self):
        return THEMES[self.theme_name]

    def set_theme(self, name):
        self.theme_name = name
        for k, v in THEMES[name].items():
            if v.startswith("#"):
                setattr(self, "t_" + k, hexc(v))
        Window.clearcolor = self.t_bg
        for d in getattr(self, "docs", []):
            d.apply_theme()
        if getattr(self, "root_w", None):
            self.refresh_tabs()
            self.set_status(self.status, self._status_kind)

    def build(self):
        Window.softinput_mode = "below_target"
        self.projects = os.path.join(self.user_data_dir, "proyectos")
        os.makedirs(self.projects, exist_ok=True)
        self.store = JsonStore(os.path.join(self.user_data_dir, "sesion.json"))
        self._status_kind = "info"
        if self.store.exists("prefs"):
            prefs = self.store.get("prefs")
            self.font_size = prefs.get("font_size", self.font_size)
            self.theme_name = prefs.get("theme", "oscuro") if prefs.get("theme") in THEMES else "oscuro"
        self.set_theme(self.theme_name)
        Builder.load_string(KV)
        self.docs = []
        self.current = None
        self.runner = Runner(self.append_output, self._set_waiting, self._run_finished)
        self.root_w = Root()
        for label, action in KEYS:
            b = FlatButton(text=label, font_size="15sp")
            b.width = max(dp(46), b.width)
            b.bind(on_release=lambda btn, a=action: self.key_action(a))
            self.root_w.ids.keybar.add_widget(b)
        Clock.schedule_once(lambda dt: self.restore_session(), 0)
        return self.root_w

    # ---------------- sesión ----------------
    def restore_session(self):
        paths = []
        if self.store.exists("session"):
            paths = [p for p in self.store.get("session")["files"] if os.path.exists(p)]
        for p in paths:
            self.open_path(p)
        if not self.docs:
            path = os.path.join(self.projects, "bienvenida.py")
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(EXAMPLES["Calculadora (tkinter)"])
            self.open_path(path)
        if self.store.exists("session"):
            idx = self.store.get("session").get("current", 0)
            if 0 <= idx < len(self.docs):
                self.select(self.docs[idx])

    def save_session(self):
        for d in self.docs:
            if d.dirty:
                d.save()
        cur = self.docs.index(self.current) if self.current in self.docs else 0
        self.store.put("session", files=[d.path for d in self.docs], current=cur)
        self.store.put("prefs", font_size=self.font_size, theme=self.theme_name)

    def on_pause(self):
        self.save_session()
        return True

    def on_stop(self):
        self.save_session()

    # ---------------- pestañas ----------------
    def refresh_tabs(self):
        box = self.root_w.ids.tabs
        box.clear_widgets()
        for d in self.docs:
            active = d is self.current
            tab = BoxLayout(size_hint_x=None)
            name = ("• " if d.dirty else "") + d.name
            b = FlatButton(text=name, font_size="13sp", bg=[0, 0, 0, 0], bg_down=self.t_btn,
                           fg=self.t_text if active else self.t_muted, bold=active)
            b.bind(on_release=lambda btn, doc=d: self.select(doc))
            x = FlatButton(text="×", font_size="20sp", width=dp(32), bg=[0, 0, 0, 0],
                           bg_down=self.t_btn, fg=self.t_muted)
            x.bind(on_release=lambda btn, doc=d: self.close_doc(doc))
            tab.add_widget(b)
            tab.add_widget(x)
            tab.width = b.width + dp(32)
            b.bind(width=lambda inst, w, t=tab: setattr(t, "width", w + dp(32)))
            if active:
                with tab.canvas.before:
                    Color(*self.t_bg)
                    tab._bgr = Rectangle(pos=tab.pos, size=tab.size)
                    Color(*self.t_accent)
                    tab._line = Rectangle(pos=tab.pos, size=(tab.width, dp(2)))

                def upd(t, *_):
                    t._bgr.pos, t._bgr.size = t.pos, t.size
                    t._line.pos, t._line.size = t.pos, (t.width, dp(2))
                tab.bind(pos=upd, size=upd)
            box.add_widget(tab)

    def select(self, doc):
        area = self.root_w.ids.editor_area
        area.clear_widgets()
        self.current = doc
        area.add_widget(doc.view)
        self.refresh_tabs()
        self.update_cursor_pos()
        self.set_status(doc.path.replace(self.projects + os.sep, ""))

    def open_path(self, path):
        for d in self.docs:
            if os.path.abspath(d.path) == os.path.abspath(path):
                self.select(d)
                return d
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            self.set_status("No se pudo abrir: %s" % e, "error")
            return None
        doc = Document(self, path, text)
        self.docs.append(doc)
        self.select(doc)
        return doc

    def close_doc(self, doc):
        if doc.dirty:
            doc.save()
        i = self.docs.index(doc)
        self.docs.remove(doc)
        if not self.docs:
            self.new_file()
        elif doc is self.current:
            self.select(self.docs[min(i, len(self.docs) - 1)])
        else:
            self.refresh_tabs()

    # ---------------- ventanas emergentes ----------------
    def popup(self, title, content, **kw):
        kw.setdefault("size_hint", (0.92, 0.85))
        return Popup(title=title, content=content, background="", background_color=self.t_panel,
                     title_color=self.t_text, title_size=sp(18), separator_color=self.t_accent,
                     separator_height=dp(1), overlay_color=(0, 0, 0, 0.5), **kw)

    def button_row(self, items):
        row = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(4))
        for text, cb, kind in items:
            colors = {"primary": (self.t_accent, self.t_on_accent), "danger": (self.t_stop, [1, 1, 1, 1]),
                      "normal": (self.t_btn, self.t_text)}[kind]
            b = FlatButton(text=text, size_hint_x=1, bg=colors[0], fg=colors[1], bold=kind != "normal")
            b.bind(on_release=cb)
            row.add_widget(b)
        return row

    def styled_input(self, **kw):
        return TextInput(multiline=False, size_hint_y=None, height=dp(50), font_size=sp(16),
                         padding=(dp(12), dp(13)), background_normal="", background_active="",
                         background_color=self.t_field, foreground_color=self.t_text,
                         cursor_color=self.t_accent, hint_text_color=self.t_muted, **kw)

    # ---------------- archivos ----------------
    def _free_name(self, base="nuevo"):
        n = 1
        while os.path.exists(os.path.join(self.projects, "%s_%d.py" % (base, n))):
            n += 1
        return os.path.join(self.projects, "%s_%d.py" % (base, n))

    def new_file(self, text="", base="nuevo"):
        path = self._free_name(base)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        self.open_path(path)

    def save_current(self):
        if self.current:
            self.current.save()
            self.set_status("Guardado: " + self.current.name, "ok")

    def open_dialog(self):
        content = BoxLayout(orientation="vertical", spacing=dp(8))
        chooser = FileChooserListView(path=self.projects, rootpath=self.projects,
                                      filters=["*.py", "*.txt", "*.json", "*.csv"])
        content.add_widget(chooser)
        popup = self.popup("Abrir archivo", content)

        def do_open(*_):
            if chooser.selection:
                self.open_path(chooser.selection[0])
                popup.dismiss()

        def do_delete(*_):
            if chooser.selection:
                target = chooser.selection[0]
                self.confirm("Eliminar", "¿Eliminar '%s'?" % os.path.basename(target),
                             lambda: self._delete(target, chooser))

        content.add_widget(self.button_row([("Eliminar", do_delete, "danger"),
                                            ("Cancelar", lambda *_: popup.dismiss(), "normal"),
                                            ("Abrir", do_open, "primary")]))
        chooser.bind(on_submit=lambda *a: do_open())
        popup.open()

    def _delete(self, path, chooser):
        for d in list(self.docs):
            if d.path == path:
                d.dirty = False
                self.close_doc(d)
        os.remove(path)
        chooser._update_files()

    def save_as_dialog(self):
        if not self.current:
            return
        content = BoxLayout(orientation="vertical", spacing=dp(12), padding=(dp(4), dp(8)))
        name = self.styled_input(text=self.current.name)
        content.add_widget(Label(text="Nombre del archivo", color=self.t_muted, size_hint_y=None, height=dp(22),
                                 halign="left", text_size=(Window.width * 0.8, None)))
        content.add_widget(name)
        popup = self.popup("Guardar como", content, size_hint=(0.9, None), height=dp(250))

        def ok(*_):
            fn = name.text.strip()
            if not fn:
                return
            if "." not in fn:
                fn += ".py"
            new = os.path.join(self.projects, fn)
            os.makedirs(os.path.dirname(new), exist_ok=True)
            self.current.path = new
            self.current.save()
            self.set_status("Guardado como " + fn, "ok")
            popup.dismiss()

        content.add_widget(self.button_row([("Cancelar", lambda *_: popup.dismiss(), "normal"),
                                            ("Guardar", ok, "primary")]))
        name.bind(on_text_validate=ok)
        popup.open()

    def confirm(self, title, msg, on_yes):
        content = BoxLayout(orientation="vertical", spacing=dp(10))
        content.add_widget(Label(text=msg, color=self.t_text, font_size=sp(16)))
        popup = self.popup(title, content, size_hint=(0.85, None), height=dp(210))
        content.add_widget(self.button_row([("No", lambda *_: popup.dismiss(), "normal"),
                                            ("Sí, eliminar", lambda *_: (popup.dismiss(), on_yes()), "danger")]))
        popup.open()

    # ---------------- menú "..." ----------------
    def open_menu(self, anchor):
        dd = DropDown(auto_width=False, width=dp(240))
        with dd.container.canvas.before:
            Color(*self.t_panel)
            bg = Rectangle()
        dd.container.bind(pos=lambda w, v: setattr(bg, "pos", v), size=lambda w, v: setattr(bg, "size", v))
        other = "claro" if self.theme_name == "oscuro" else "oscuro"
        items = [
            ("Guardar como...", self.save_as_dialog),
            ("Ejemplos", self.examples_dialog),
            ("Ir a línea...", self.goto_dialog),
            ("Cerrar pestaña", lambda: self.current and self.close_doc(self.current)),
            ("Texto más grande", lambda: self.zoom(1)),
            ("Texto más pequeño", lambda: self.zoom(-1)),
            ("Tema " + other, lambda: self.set_theme(other)),
            ("Acerca de", self.about),
        ]
        for text, cb in items:
            b = FlatButton(text=text, size_hint=(1, None), height=dp(50), bg=[0, 0, 0, 0],
                           halign="left", valign="middle", padding=(dp(16), 0))
            b.bind(size=lambda w, v: setattr(w, "text_size", v))
            b.bind(on_release=lambda btn, f=cb: (dd.dismiss(), f()))
            dd.add_widget(b)
        dd.open(anchor)

    def examples_dialog(self):
        content = BoxLayout(orientation="vertical", spacing=dp(4))
        sv = ScrollView()
        lst = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(2))
        lst.bind(minimum_height=lst.setter("height"))
        popup = self.popup("Ejemplos", content)
        for name, code in EXAMPLES.items():
            b = FlatButton(text=name, size_hint=(1, None), height=dp(56), halign="left", valign="middle",
                           padding=(dp(16), 0))
            b.bind(size=lambda w, v: setattr(w, "text_size", v))
            base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
            b.bind(on_release=lambda btn, c=code, n=base: (popup.dismiss(), self.new_file(c, n)))
            lst.add_widget(b)
        sv.add_widget(lst)
        content.add_widget(sv)
        popup.open()

    def goto_dialog(self):
        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=(dp(4), dp(8)))
        num = self.styled_input(input_filter="int", hint_text="Número de línea")
        content.add_widget(num)
        popup = self.popup("Ir a línea", content, size_hint=(0.8, None), height=dp(170))

        def go(*_):
            if num.text:
                self.goto_line(int(num.text))
            popup.dismiss()

        num.bind(on_text_validate=go)
        popup.open()
        Clock.schedule_once(lambda dt: setattr(num, "focus", True), 0.2)

    def goto_line(self, n, select=False):
        ed = self.current.editor
        row = max(0, min(n - 1, len(ed._lines) - 1))
        ed.cursor = (0, row)
        if select:
            start = ed.cursor_index((0, row))
            ed.select_text(start, start + len(ed._lines[row]))
        ed.focus = True

    def zoom(self, step):
        self.font_size = max(sp(9), min(sp(30), self.font_size + sp(step)))
        for d in self.docs:
            d.editor.font_size = self.font_size
        self.root_w.ids.console.font_size = self.font_size * 0.9

    def about(self):
        content = Label(text="[b]PyStudio Móvil[/b]\n\nIDE de Python para Android\nPython %s\n"
                             "Capa compatible tkinter sobre Kivy" % sys.version.split()[0],
                        markup=True, halign="center", color=self.t_text, font_size=sp(15))
        self.popup("Acerca de", content, size_hint=(0.85, None), height=dp(260)).open()

    # ---------------- teclas rápidas ----------------
    def key_action(self, action):
        if not self.current:
            return
        ed = self.current.editor
        moves = {"@left": "cursor_left", "@right": "cursor_right",
                 "@up": "cursor_up", "@down": "cursor_down"}
        if action in moves:
            ed.do_cursor_movement(moves[action])
        elif action == "@undo":
            ed.do_undo()
        elif action == "@redo":
            ed.do_redo()
        else:
            ed.insert_text(action)
        ed.focus = True

    def update_cursor_pos(self, *_):
        if self.current:
            col, row = self.current.editor.cursor
            self.cursor_pos = "Ln %d, Col %d" % (row + 1, col + 1)

    def set_status(self, text, kind="info"):
        self.status = text
        self._status_kind = kind
        self.status_color = {"info": self.t_accent, "ok": self.t_run, "error": self.t_stop,
                             "run": hexc("#e3b341")}[kind]

    # ---------------- ejecución ----------------
    def toggle_run(self):
        if self.running:
            self.runner.stop()
            self.set_status("Deteniendo...", "run")
        else:
            self.run_current()

    def run_current(self):
        if not self.current:
            return
        self.current.save()
        self.clear_console()
        self.append_output(">>> %s\n" % self.current.name)
        self._run_doc = self.current
        self._run_start = time.time()
        self._run_log = []
        self.running = True
        self.set_status("Ejecutando " + self.current.name, "run")
        self.runner.run(self.current.editor.text, self.current.path)

    def _run_finished(self, status):
        self.running = False
        self.waiting_input = False
        secs = time.time() - self._run_start
        if status == 0:
            self.append_output("\n[Terminado en %.2f s]\n" % secs)
            self.set_status("Ejecución correcta (%.2f s)" % secs, "ok")
        elif status == 2:
            self.set_status("Ejecución detenida", "info")
        else:
            self.append_output("\n[Terminó con errores]\n")
            log = "".join(self._run_log)
            m = re.findall(r'File "%s", line (\d+)' % re.escape(self._run_doc.path), log)
            last = log.strip().splitlines()[-1] if log.strip() else "Error"
            self.set_status(last, "error")
            if m and self._run_doc is self.current:
                self.goto_line(int(m[-1]), select=True)

    def append_output(self, text):
        if self.running and hasattr(self, "_run_log"):
            self._run_log.append(text)
        con = self.root_w.ids.console
        new = con.text + text
        if len(new) > 200000:
            new = new[-150000:]
        con.text = new
        Clock.schedule_once(lambda dt: setattr(con, "cursor", con.get_cursor_from_index(len(con.text))), 0)

    def clear_console(self):
        self.root_w.ids.console.text = ""

    def _set_waiting(self, value):
        self.waiting_input = value
        if value:
            Clock.schedule_once(lambda dt: setattr(self.root_w.ids.stdin, "focus", True), 0.1)

    def send_input(self):
        box = self.root_w.ids.stdin
        if self.waiting_input:
            self.runner.send_input(box.text)
            box.text = ""


if __name__ == "__main__":
    PyStudioApp().run()
