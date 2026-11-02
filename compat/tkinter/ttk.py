"""tkinter.ttk sobre Kivy: mismos widgets con soporte de style/padding y extras."""
import tkinter as _tk
from kivy.clock import Clock as _Clock
from kivy.metrics import dp as _dp
from kivy.uix.boxlayout import BoxLayout as _KBox
from kivy.uix.button import Button as _KButton
from kivy.uix.label import Label as _KLabel
from kivy.uix.progressbar import ProgressBar as _KProgressBar
from kivy.uix.scrollview import ScrollView as _KScrollView
from kivy.uix.spinner import Spinner as _KSpinner
from kivy.utils import get_color_from_hex as _hex

from tkinter import (_TkPanel, _Container, _color, _font, _later, _post, _px, _text_size, _ui,  # noqa: F401
                     DEFAULT_FS, END, HORIZONTAL, VERTICAL, DISABLED, NORMAL, LEFT, TOP, BOTH, X, Y, W, E, N, S,
                     CENTER, NSEW, StringVar, IntVar, DoubleVar, BooleanVar, TclError)


def _strip(kw):
    kw.pop("style", None)
    kw.pop("takefocus", None)
    pad = kw.pop("padding", None)
    if pad is not None:
        if isinstance(pad, (list, tuple)):
            pad = pad[0] if pad else 0
        else:
            pad = str(pad).split()[0]
        kw.setdefault("padx", pad)
        kw.setdefault("pady", pad)
    return kw


def _wrap(base):
    class W_(base):
        def __init__(self, master=None, **kw):
            super().__init__(master, **_strip(kw))

        def configure(self, cnf=None, **kw):
            return super().configure(cnf, **_strip(kw))

        config = configure

        def state(self, statespec=None):
            if statespec:
                for s in statespec:
                    if s == "disabled":
                        self.configure(state=DISABLED)
                    elif s == "!disabled":
                        self.configure(state=NORMAL)
            return ()

        def instate(self, statespec, callback=None, *a):
            dis = self._opts.get("state") == DISABLED
            ok = all((s == "disabled") == dis if not s.startswith("!") else (s[1:] == "disabled") != dis
                     for s in statespec)
            if ok and callback:
                return callback(*a)
            return ok

    W_.__name__ = base.__name__
    W_.__qualname__ = base.__name__
    return W_


Button = _wrap(_tk.Button)
Label = _wrap(_tk.Label)
Entry = _wrap(_tk.Entry)
Frame = _wrap(_tk.Frame)
LabelFrame = Labelframe = _wrap(_tk.LabelFrame)
Checkbutton = _wrap(_tk.Checkbutton)
Radiobutton = _wrap(_tk.Radiobutton)
Scale = _wrap(_tk.Scale)
Scrollbar = _wrap(_tk.Scrollbar)
Spinbox = _wrap(_tk.Spinbox)
Menubutton = _wrap(_tk.Menubutton)
PanedWindow = Panedwindow = _wrap(_tk.PanedWindow)


class LabeledScale(Scale):
    pass


class OptionMenu(_tk.OptionMenu):
    def __init__(self, master, variable, default=None, *values, **kw):
        kw.pop("style", None)
        if default is not None:
            variable.set(default)
        super().__init__(master, variable, *(values or (default,)), **kw)


class Sizegrip(_tk.Widget):
    def _req(self):
        return 0, 0


class Separator(_tk.Widget):
    _defaults = {"orient": HORIZONTAL}

    def _create(self):
        return _TkPanel(bg=[0.7, 0.7, 0.7, 1])

    def _req(self):
        return (_dp(2), _dp(2))


class Style:
    def __init__(self, master=None):
        pass

    def configure(self, style, query_opt=None, **kw):
        return {}

    def map(self, style, query_opt=None, **kw):
        return {}

    def lookup(self, style, option, state=None, default=None):
        return default or ""

    def layout(self, style, layoutspec=None):
        return []

    def element_create(self, *a, **k):
        pass

    def theme_names(self):
        return ("default", "clam", "alt", "classic")

    def theme_use(self, themename=None):
        return "default"

    def theme_create(self, *a, **k):
        pass

    theme_settings = theme_create


class Combobox(_tk.Widget):
    _defaults = {"width": 20, "values": ()}

    def _create(self):
        kv = _KSpinner(text="", values=[], font_size=DEFAULT_FS, background_normal="", background_down="",
                       background_color=(0, 0, 0, 0), color=(0.1, 0.1, 0.12, 1), sync_height=True,
                       halign="left", valign="middle", padding=(_dp(12), 0))
        kv.bind(size=lambda w, v: setattr(w, "text_size", v))
        from kivy.graphics import Color, Line, RoundedRectangle
        with kv.canvas.before:
            Color(1, 1, 1, 1)
            bg = RoundedRectangle(radius=[_dp(10)])
            Color(0.78, 0.8, 0.84, 1)
            border = Line(width=_dp(1))
            Color(0.45, 0.47, 0.52, 1)
            arrow = Line(width=_dp(1.5))

        def upd(w, *a):
            bg.pos, bg.size = w.pos, w.size
            border.rounded_rectangle = (w.x, w.y, w.width, w.height, _dp(10))
            ax, ay = w.right - _dp(20), w.center_y
            arrow.points = [ax - _dp(5), ay + _dp(3), ax, ay - _dp(2), ax + _dp(5), ay + _dp(3)]
        kv.bind(pos=upd, size=upd)
        kv.bind(text=self._on_text)
        self._quiet = False
        return kv

    def __init__(self, master=None, **kw):
        super().__init__(master, **_strip(kw))

    def _on_text(self, kv, text):
        var = self._opts.get("textvariable")
        if var is not None:
            var._set_from_ui(text)
        if not self._quiet:
            self._fire("<<ComboboxSelected>>")

    def _apply(self, kw):
        kv = self._kv
        if "values" in kw:
            vals = kw["values"]
            if isinstance(vals, str):
                vals = vals.split()
            kv.values = [str(v) for v in (vals or ())]
        if "textvariable" in kw and kw["textvariable"] is not None:
            def setter(v):
                self._quiet = True
                kv.text = str(v)
                self._quiet = False
            self._bind_var(kw["textvariable"], setter)
        if "state" in kw:
            kv.disabled = kw["state"] == DISABLED
        if "font" in kw:
            for k, v in _font(kw["font"]).items():
                if hasattr(kv, k):
                    setattr(kv, k, v)

    def _req(self):
        fs = self._kv.font_size
        return max(float(self._opts.get("width", 20)) * fs * 0.55, _dp(80)) + _dp(20), max(fs * 1.25 + _dp(20), _dp(44))

    def get(self):
        return self._kv.text

    def set(self, value):
        def do():
            self._quiet = True
            self._kv.text = str(value)
            self._quiet = False
        _ui(do)

    def current(self, newindex=None):
        vals = list(self._kv.values)
        if newindex is None:
            return vals.index(self._kv.text) if self._kv.text in vals else -1
        self.set(vals[int(newindex)])

    def delete(self, first, last=None):
        self.set("")

    def insert(self, index, string):
        self.set(self.get() + str(string))


class Progressbar(_tk.Widget):
    _defaults = {"orient": HORIZONTAL, "length": 200, "maximum": 100, "value": 0, "mode": "determinate"}

    def _create(self):
        self._anim = None
        return _KProgressBar(max=100, value=0)

    def __init__(self, master=None, **kw):
        super().__init__(master, **_strip(kw))

    def _apply(self, kw):
        kv = self._kv
        if "maximum" in kw:
            kv.max = float(kw["maximum"])
        if "value" in kw:
            kv.value = float(kw["value"])
        if "variable" in kw and kw["variable"] is not None:
            self._bind_var(kw["variable"], lambda v: setattr(kv, "value", float(v)))

    def _req(self):
        length = _px(self._opts.get("length", 200))
        return (length, _dp(24)) if self._opts.get("orient", HORIZONTAL) == HORIZONTAL else (_dp(24), length)

    def cget(self, key):
        if key == "value":
            return self._kv.value
        return super().cget(key)

    __getitem__ = cget

    def step(self, amount=1.0):
        def do():
            kv = self._kv
            v = kv.value + float(amount)
            kv.value = v % kv.max if v > kv.max else v
            self._opts["value"] = kv.value
        _ui(do)

    def start(self, interval=50):
        def do():
            if self._anim is None:
                self._anim = _Clock.schedule_interval(
                    lambda dt: setattr(self._kv, "value", (self._kv.value + 1) % (self._kv.max + 1)), interval / 1000.0)
        _ui(do)

    def stop(self):
        def do():
            if self._anim is not None:
                self._anim.cancel()
                self._anim = None
        _ui(do)


class Notebook(_tk.Widget, _Container):
    def _create(self):
        self._tabs = []
        self._cur = 0
        kv = _TkPanel(bg=[0.94, 0.94, 0.94, 1])
        self._bar = _KBox(size_hint=(None, None), height=_dp(42), spacing=_dp(2))
        kv.add_widget(self._bar)
        return kv

    def __init__(self, master=None, **kw):
        super().__init__(master, **_strip(kw))

    def _render(self):
        self._bar.clear_widgets()
        for i, (child, text) in enumerate(self._tabs):
            on = i == self._cur
            b = _KButton(text=str(text), background_normal="", font_size=DEFAULT_FS * 0.95,
                         background_color=_hex("#ffffff") if on else _hex("#d6d6d6"),
                         color=(0, 0.35, 0.7, 1) if on else (0.2, 0.2, 0.2, 1), bold=on)
            b.bind(on_release=lambda w, idx=i: self._choose(idx))
            self._bar.add_widget(b)

    def _choose(self, idx):
        self._cur = idx
        self._render()
        self._relayout()
        self._fire("<<NotebookTabChanged>>")

    def add(self, child, text="", **kw):
        self._tabs.append((child, kw.get("text", text)))
        child._geom = ("nb", {})
        _ui(self._render)
        self._relayout()

    def insert(self, pos, child, **kw):
        self.add(child, **kw)

    def forget(self, tab_id):
        i = self.index(tab_id)
        self._tabs.pop(i)
        self._cur = min(self._cur, max(0, len(self._tabs) - 1))
        _ui(self._render)
        self._relayout()

    hide = forget

    def select(self, tab_id=None):
        if tab_id is None:
            return self._tabs[self._cur][0] if self._tabs else None
        _ui(self._choose, self.index(tab_id))

    def index(self, tab_id):
        if tab_id == END:
            return len(self._tabs)
        if isinstance(tab_id, int):
            return tab_id
        if tab_id == "current":
            return self._cur
        for i, (c, t) in enumerate(self._tabs):
            if c is tab_id or str(c) == str(tab_id):
                return i
        raise TclError("tab not found")

    def tab(self, tab_id, option=None, **kw):
        i = self.index(tab_id)
        if "text" in kw:
            self._tabs[i] = (self._tabs[i][0], kw["text"])
            _ui(self._render)
        return {"text": self._tabs[i][1]} if option is None else self._tabs[i][1]

    def tabs(self):
        return tuple(c for c, t in self._tabs)

    def _req(self):
        w = h = 0
        for c, t in self._tabs:
            cw, ch = c._req()
            w, h = max(w, cw), max(h, ch)
        return max(w, _dp(200)), h + _dp(46)

    def _arrange(self):
        kv = self._kv
        self._bar.width = kv.width
        self._bar.pos = (kv.x, kv.top - self._bar.height)
        for i, (c, t) in enumerate(self._tabs):
            ckv = c._kv
            if i != self._cur:
                if ckv.parent is not None:
                    ckv.parent.remove_widget(ckv)
                continue
            if ckv.parent is not kv:
                if ckv.parent is not None:
                    ckv.parent.remove_widget(ckv)
                kv.add_widget(ckv)
            ckv.size_hint = (None, None)
            ckv.pos = (kv.x, kv.y)
            ckv.size = (kv.width, max(0, kv.height - self._bar.height - _dp(2)))
            if isinstance(c, _Container):
                c._arrange()


class Treeview(_tk.Widget):
    """Tabla sencilla: columnas, encabezados, filas, selección."""
    _defaults = {"columns": (), "show": "tree headings", "height": 10, "selectmode": "extended"}

    def __init__(self, master=None, **kw):
        self._rows = {}
        self._iids = []
        self._sel = []
        self._heads = {}
        self._colopts = {}
        self._n = 0
        super().__init__(master, **_strip(kw))

    def _create(self):
        box = _KBox(orientation="vertical")
        self._head = _KBox(size_hint_y=None, height=_dp(40))
        sv = _KScrollView(do_scroll_x=False, bar_width=_dp(4))
        self._body = _KBox(orientation="vertical", size_hint_y=None)
        self._body.bind(minimum_height=self._body.setter("height"))
        sv.add_widget(self._body)
        box.add_widget(self._head)
        box.add_widget(sv)
        return box

    def _cols(self):
        cols = self._opts.get("columns") or ()
        if isinstance(cols, str):
            cols = cols.split()
        return list(cols)

    def _show_tree(self):
        return "tree" in str(self._opts.get("show", "tree headings"))

    def _apply(self, kw):
        self._render()

    def _render(self):
        cols = self._cols()
        keys = (["#0"] if self._show_tree() else []) + cols
        self._head.clear_widgets()
        if "headings" in str(self._opts.get("show", "tree headings")):
            for k in keys:
                lbl = _KButton(text=str(self._heads.get(k, {}).get("text", "" if k == "#0" else k)), bold=True,
                               background_normal="", background_color=_hex("#e4e4e4"), color=(0, 0, 0, 1),
                               font_size=DEFAULT_FS * 0.9)
                cmd = self._heads.get(k, {}).get("command")
                if cmd:
                    lbl.bind(on_release=lambda w, c=cmd: _post(c))
                self._head.add_widget(lbl)
            self._head.height = _dp(40)
        else:
            self._head.height = 0
        self._body.clear_widgets()
        for iid in self._iids:
            r = self._rows[iid]
            on = iid in self._sel
            row = _KBox(size_hint_y=None, height=_dp(42))
            vals = list(r["values"]) + [""] * len(cols)
            cells = ([r["text"]] if self._show_tree() else []) + [vals[i] for i in range(len(cols))]
            for v in cells:
                b = _KButton(text=str(v), background_normal="", background_down="",
                             background_color=_hex("#0078d7") if on else (1, 1, 1, 1),
                             color=(1, 1, 1, 1) if on else (0, 0, 0, 1), font_size=DEFAULT_FS * 0.9,
                             halign="left", valign="middle", padding=(_dp(8), 0), shorten=True)
                b.bind(size=lambda w, s: setattr(w, "text_size", s))
                b.bind(on_release=lambda w, i=iid: self._click(i))
                row.add_widget(b)
            self._body.add_widget(row)

    def _click(self, iid):
        if self._opts.get("selectmode") == "extended" and False:
            pass
        self._sel = [iid]
        self._render()
        self._fire("<<TreeviewSelect>>")

    def _req(self):
        ncol = len(self._cols()) + (1 if self._show_tree() else 0)
        return max(_dp(120) * max(1, ncol), _dp(200)), _dp(40) + float(self._opts.get("height", 10)) * _dp(42)

    def heading(self, column, option=None, **kw):
        self._heads.setdefault(column, {}).update(kw)
        _ui(self._render)
        return self._heads[column] if option is None else self._heads[column].get(option)

    def column(self, column, option=None, **kw):
        self._colopts.setdefault(column, {}).update(kw)
        return self._colopts[column] if option is None else self._colopts[column].get(option)

    def insert(self, parent, index, iid=None, **kw):
        self._n += 1
        iid = iid or "I%03X" % self._n
        self._rows[iid] = {"text": kw.get("text", ""), "values": tuple(kw.get("values", ())),
                           "tags": kw.get("tags", ()), "parent": parent}
        if index in (END, "end") or int(index) >= len(self._iids):
            self._iids.append(iid)
        else:
            self._iids.insert(int(index), iid)
        _ui(self._render)
        return iid

    def delete(self, *items):
        for iid in items:
            if iid in self._rows:
                del self._rows[iid]
                self._iids.remove(iid)
            if iid in self._sel:
                self._sel.remove(iid)
        _ui(self._render)

    detach = delete

    def get_children(self, item=None):
        return tuple(i for i in self._iids if not item or self._rows[i]["parent"] == item)

    def item(self, iid, option=None, **kw):
        r = self._rows[iid]
        if kw:
            if "values" in kw:
                kw["values"] = tuple(kw["values"])
            r.update(kw)
            _ui(self._render)
            return None
        d = {"text": r["text"], "values": list(r["values"]), "tags": r["tags"], "image": "", "open": 0}
        return d if option is None else d.get(option)

    def set(self, item, column=None, value=None):
        cols = self._cols()
        vals = list(self._rows[item]["values"]) + [""] * len(cols)
        if column is None:
            return dict(zip(cols, vals))
        i = cols.index(column) if column in cols else int(str(column).lstrip("#")) - 1
        if value is None:
            return vals[i]
        vals[i] = value
        self._rows[item]["values"] = tuple(vals[:len(cols)])
        _ui(self._render)

    def selection(self):
        return tuple(self._sel)

    def selection_set(self, *items):
        if len(items) == 1 and isinstance(items[0], (list, tuple)):
            items = items[0]
        self._sel = [i for i in items if i in self._rows]
        _ui(self._render)

    def selection_remove(self, *items):
        self._sel = [i for i in self._sel if i not in items]
        _ui(self._render)

    def focus(self, item=None):
        return self._sel[0] if self._sel else ""

    def index(self, item):
        return self._iids.index(item)

    def exists(self, item):
        return item in self._rows

    def parent(self, item):
        return self._rows[item]["parent"]

    def move(self, item, parent, index):
        self._iids.remove(item)
        self._iids.insert(int(index) if index != END else len(self._iids), item)
        _ui(self._render)

    def see(self, item):
        pass

    def tag_configure(self, *a, **k):
        pass

    tag_bind = identify_row = identify_column = yview = xview = tag_configure
