"""Capa compatible de tkinter para PyStudio (Android).

Android no trae Tk, así que este módulo reimplementa la API más usada de
tkinter sobre Kivy. El código del usuario corre en un hilo de trabajo; todas
las operaciones gráficas se envían al hilo principal de Kivy (_ui) y los
callbacks (command=, bind, after) vuelven al hilo del usuario a través de la
cola que procesa mainloop(), igual que en Tk real.

Incluye: Tk, Toplevel, Frame, LabelFrame, Label, Button, Entry, Text,
Checkbutton, Radiobutton, Listbox, Scale, Canvas, Spinbox, Message,
StringVar/IntVar/DoubleVar/BooleanVar, pack/grid/place, after, bind,
messagebox, simpledialog y ttk (Combobox, Progressbar, ...).
"""
import queue as _queue
import re as _re
import sys as _sys
import threading as _threading
import time as _time
import traceback as _traceback

from kivy.clock import Clock as _Clock
from kivy.core.text import Label as _CoreLabel
from kivy.core.window import Window as _Window
from kivy.graphics import Color as _GColor, Ellipse as _GEllipse, Line as _GLine, \
    Mesh as _GMesh, Rectangle as _GRect
from kivy.lang import Builder as _Builder
from kivy.metrics import dp as _dp, sp as _sp
from kivy.properties import ListProperty as _ListProperty
from kivy.uix.boxlayout import BoxLayout as _KBox
from kivy.uix.button import Button as _KButton
from kivy.uix.checkbox import CheckBox as _KCheckBox
from kivy.uix.label import Label as _KLabel
from kivy.uix.modalview import ModalView as _KModalView
from kivy.uix.popup import Popup as _KPopup
from kivy.uix.progressbar import ProgressBar as _KProgressBar
from kivy.uix.scrollview import ScrollView as _KScrollView
from kivy.uix.slider import Slider as _KSlider
from kivy.uix.spinner import Spinner as _KSpinner
from kivy.uix.stencilview import StencilView as _KStencil
from kivy.uix.textinput import TextInput as _KTextInput
from kivy.uix.widget import Widget as _KWidget
from kivy.utils import colormap as _colormap, get_color_from_hex as _hex

import runtime as _runtime

TkVersion = 8.6
TclVersion = 8.6
wantobjects = 1

# ---------------------------------------------------------------- constantes
NO = FALSE = OFF = 0
YES = TRUE = ON = 1
N, S, W, E = "n", "s", "w", "e"
NW, SW, NE, SE = "nw", "sw", "ne", "se"
NS, EW, NSEW = "ns", "ew", "nsew"
CENTER = "center"
NONE, X, Y, BOTH = "none", "x", "y", "both"
LEFT, TOP, RIGHT, BOTTOM = "left", "top", "right", "bottom"
RAISED, SUNKEN, FLAT, RIDGE, GROOVE, SOLID = "raised", "sunken", "flat", "ridge", "groove", "solid"
HORIZONTAL, VERTICAL = "horizontal", "vertical"
NUMERIC = "numeric"
CHAR, WORD = "char", "word"
BASELINE = "baseline"
INSIDE, OUTSIDE = "inside", "outside"
SEL = "sel"
SEL_FIRST, SEL_LAST = "sel.first", "sel.last"
END = "end"
INSERT = "insert"
CURRENT = "current"
ANCHOR = "anchor"
ALL = "all"
NORMAL, DISABLED, ACTIVE, HIDDEN = "normal", "disabled", "active", "hidden"
CASCADE, CHECKBUTTON, COMMAND, RADIOBUTTON, SEPARATOR = "cascade", "checkbutton", "command", "radiobutton", "separator"
SINGLE, BROWSE, MULTIPLE, EXTENDED = "single", "browse", "multiple", "extended"
DOTBOX, UNDERLINE = "dotbox", "underline"
PIESLICE, CHORD, ARC = "pieslice", "chord", "arc"
FIRST, LAST, BUTT, PROJECTING, ROUND, BEVEL, MITER = "first", "last", "butt", "projecting", "round", "bevel", "miter"
MOVETO, SCROLL, UNITS, PAGES = "moveto", "scroll", "units", "pages"


class TclError(Exception):
    pass


# ---------------------------------------------------------------- estado / hilos
class _State:
    def __init__(self, stop):
        self.stop = stop
        self.events = _queue.Queue()
        self.roots = []
        self.default_root = None
        self.mainloop_called = False
        self.quit = False
        self.after = {}
        self.after_n = 0


_st = _State(_runtime.CURRENT_STOP)
_MAIN = _threading.main_thread()


def _is_main():
    return _threading.current_thread() is _MAIN


def _check_stop():
    if _st.stop.is_set():
        raise _runtime.StopExecution()


def _ui(fn, *a, **k):
    """Ejecuta fn en el hilo de Kivy y espera el resultado."""
    if _is_main():
        return fn(*a, **k)
    box = {}
    done = _threading.Event()

    def job(dt):
        try:
            box["r"] = fn(*a, **k)
        except BaseException as e:  # noqa
            box["e"] = e
        done.set()

    _Clock.schedule_once(job, 0)
    while not done.wait(0.05):
        _check_stop()
    if "e" in box:
        raise box["e"]
    return box.get("r")


def _later(fn, *a):
    """Programa fn en el hilo de Kivy sin esperar."""
    if _is_main():
        fn(*a)
    else:
        _Clock.schedule_once(lambda dt: fn(*a), 0)


def _post(fn, *a):
    """Encola un callback del usuario para que lo ejecute mainloop()."""
    if fn is not None:
        _st.events.put((fn, a))


def _call_user(fn, *a):
    if fn is None:
        return
    if _is_main():
        _post(fn, *a)
    else:
        fn(*a)


def _run_cb(fn, a):
    try:
        fn(*a)
    except _runtime.StopExecution:
        raise
    except SystemExit:
        for r in list(_st.roots):
            r.destroy()
        raise
    except Exception:
        _sys.stderr.write("Exception in Tkinter callback\n")
        _traceback.print_exc()


def _reset(stop_event):
    global _st
    _shutdown()
    _st = _State(stop_event)


def _shutdown():
    for r in list(_st.roots):
        r._alive = False
        view = getattr(r, "_view", None)
        if view is not None:
            _Clock.schedule_once(lambda dt, v=view: v.dismiss(animation=False), 0)
    _st.roots.clear()
    for ev in _st.after.values():
        ev.cancel()
    _st.after.clear()
    _later(lambda: _Window.unbind(on_keyboard=_on_back))


def _pending_mainloop():
    if not _st.mainloop_called and any(r._alive and r._visible for r in _st.roots):
        mainloop()


def mainloop(n=0):
    _st.mainloop_called = True
    _st.quit = False
    while True:
        _check_stop()
        root = _st.default_root
        if _st.quit or root is None or not root._alive:
            break
        try:
            fn, a = _st.events.get(timeout=0.05)
        except _queue.Empty:
            continue
        _run_cb(fn, a)


def _process_events():
    _check_stop()
    while True:
        try:
            fn, a = _st.events.get_nowait()
        except _queue.Empty:
            break
        _run_cb(fn, a)


def _get_default_root(what=None):
    if _st.default_root is None or not _st.default_root._alive:
        Tk()
    return _st.default_root


def _on_back(window, key, *a):
    if key == 27:
        alive = [r for r in _st.roots if r._alive and r._visible]
        if alive:
            alive[-1]._on_close()
            return True
    return False


# ---------------------------------------------------------------- utilidades
_TK_COLORS = {
    "systembuttonface": "#f0f0f0", "systemwindow": "#ffffff", "systemwindowtext": "#000000",
    "systembuttontext": "#000000", "systemhighlight": "#0078d7", "systemhighlighttext": "#ffffff",
    "systemtransparent": "#00000000",
}


def _color(c, default=None):
    if c is None or c == "":
        return default
    if isinstance(c, (list, tuple)):
        return list(c)
    s = str(c).strip().lower().replace(" ", "")
    s = _TK_COLORS.get(s, s)
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        elif len(h) == 12:
            h = h[0:2] + h[4:6] + h[8:10]
        try:
            return list(_hex("#" + h))
        except Exception:
            return default
    if s in _colormap:
        return list(_colormap[s])
    base = s.rstrip("0123456789")
    if base in _colormap:
        return list(_colormap[base])
    if base in ("gray", "grey") and s[len(base):]:
        v = int(s[len(base):]) / 100.0
        return [v, v, v, 1]
    return default


def _font(f):
    """Convierte una fuente tkinter a propiedades de Kivy."""
    if f is None or f == "":
        return {}
    if hasattr(f, "actual"):
        f = (f.actual("family"), f.actual("size"), f.actual("weight"), f.actual("slant"))
    if isinstance(f, str):
        m = _re.match(r"\{([^}]*)\}\s*(.*)", f)
        parts = [m.group(1)] + m.group(2).split() if m else f.split()
    else:
        parts = list(f)
    family = str(parts[0]).lower() if parts else ""
    size = 10
    bold = italic = False
    for p in parts[1:]:
        try:
            size = int(p)
            continue
        except (TypeError, ValueError):
            pass
        p = str(p).lower()
        bold = bold or "bold" in p
        italic = italic or "italic" in p
    px = _dp(-size) if size < 0 else _sp(size * 1.33)
    mono = family in ("courier", "courier new", "consolas", "monospace", "tkfixedfont", "lucida console",
                      "fixed", "menlo", "monaco")
    return {"font_size": px, "bold": bold, "italic": italic,
            "font_name": "RobotoMono-Regular" if mono else "Roboto"}


def _px(v, default=0):
    """Distancias tk (píxeles) a píxeles de Kivy."""
    if v is None or v == "":
        return default
    try:
        return _dp(float(v))
    except (TypeError, ValueError):
        s = str(v)
        mult = {"c": 37.8, "m": 3.78, "i": 96, "p": 1.33}.get(s[-1:], 1)
        try:
            return _dp(float(s[:-1]) * mult)
        except ValueError:
            return default


def _pad(v):
    if isinstance(v, (tuple, list)):
        return _px(v[0]), _px(v[1] if len(v) > 1 else v[0])
    p = _px(v)
    return p, p


def _truthy(v):
    if isinstance(v, str):
        return v.lower() in ("1", "yes", "true", "on")
    return bool(v)


DEFAULT_FS = _sp(15)
TK_BG = "#f5f6f8"
BTN_BG = "#e4e7ec"
ACCENT = "#1a73e8"
RADIUS = _dp(10)

_Builder.load_string("""
<_TkButton>:
    background_normal: ''
    background_down: ''
    background_disabled_normal: ''
    background_color: 0, 0, 0, 0
    canvas.before:
        Color:
            rgba: self.fill if not self.disabled else (self.fill[0], self.fill[1], self.fill[2], 0.45)
        RoundedRectangle:
            pos: self.x + dp(2), self.y + dp(2)
            size: max(0, self.width - dp(4)), max(0, self.height - dp(4))
            radius: [dp(10)]
<_TkField>:
    background_normal: ''
    background_active: ''
    background_disabled_normal: ''
    background_color: 0, 0, 0, 0
    canvas.before:
        Color:
            rgba: self.fill
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]
        Color:
            rgba: (0.1, 0.45, 0.91, 1) if self.focus else (0.78, 0.8, 0.84, 1)
        Line:
            rounded_rectangle: self.x, self.y, self.width, self.height, dp(10)
            width: dp(1.4) if self.focus else dp(1)
<_TkPanel>:
    canvas.before:
        Color:
            rgba: self.bg
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: self.border
        Line:
            rectangle: self.x + 1, self.y + 1, self.width - 2, self.height - 2
            width: 1
<_TkLabel>:
    canvas.before:
        Color:
            rgba: self.bg
        Rectangle:
            pos: self.pos
            size: self.size
""")


class _TkPanel(_KWidget):
    bg = _ListProperty([0, 0, 0, 0])
    border = _ListProperty([0, 0, 0, 0])


class _TkLabel(_KLabel):
    bg = _ListProperty([0, 0, 0, 0])


class _TkButton(_KButton):
    fill = _ListProperty(list(_hex(BTN_BG)))


class _TkField(_KTextInput):
    fill = _ListProperty([1, 1, 1, 1])


def _button_fg(fill):
    """Texto blanco sobre fondos oscuros, oscuro sobre fondos claros."""
    lum = 0.299 * fill[0] + 0.587 * fill[1] + 0.114 * fill[2]
    return [1, 1, 1, 1] if lum < 0.6 else [0.12, 0.12, 0.14, 1]


class Event:
    def __init__(self, widget=None, **kw):
        self.widget = widget
        self.x = self.y = self.x_root = self.y_root = 0
        self.char = ""
        self.keysym = ""
        self.keycode = 0
        self.num = 1
        self.delta = 0
        self.width = self.height = 0
        self.type = ""
        self.__dict__.update(kw)

    def __repr__(self):
        return "<Event %s x=%s y=%s>" % (self.type, self.x, self.y)


# ---------------------------------------------------------------- variables
class Variable:
    _default = ""
    _n = 0

    def __init__(self, master=None, value=None, name=None):
        Variable._n += 1
        self._name = name or "PY_VAR%d" % Variable._n
        self._value = self._default if value is None else self._coerce(value)
        self._listeners = []
        self._traces = {}

    def _coerce(self, v):
        return v

    def __str__(self):
        return self._name

    def set(self, value):
        self._value = self._coerce(value)
        self._notify(from_ui=False)

    initialize = set

    def get(self):
        return self._value

    def _set_from_ui(self, value):
        try:
            v = self._coerce(value)
        except (TypeError, ValueError):
            return
        if v != self._value:
            self._value = v
            self._notify(from_ui=True)

    def _notify(self, from_ui):
        v = self._value
        if not from_ui:
            for f in list(self._listeners):
                _later(f, v)
        for cb in list(self._traces.values()):
            if from_ui:
                _post(cb, self._name, "", "write")
            else:
                cb(self._name, "", "write")

    def _listen(self, fn):
        self._listeners.append(fn)
        _later(fn, self._value)

    def _unlisten(self, fn):
        if fn in self._listeners:
            self._listeners.remove(fn)

    def trace_add(self, mode, callback):
        cbname = "trace%d" % (len(self._traces) + 1)
        modes = mode if isinstance(mode, (list, tuple)) else [mode]
        if any(m in ("write", "w") for m in modes):
            self._traces[cbname] = callback
        return cbname

    def trace(self, mode, callback):
        return self.trace_add(mode, callback)

    trace_variable = trace

    def trace_remove(self, mode, cbname):
        self._traces.pop(cbname, None)

    trace_vdelete = lambda self, mode, cbname: self.trace_remove(mode, cbname)

    def trace_info(self):
        return [(("write",), n) for n in self._traces]


class StringVar(Variable):
    _default = ""

    def _coerce(self, v):
        return str(v)


class IntVar(Variable):
    _default = 0

    def _coerce(self, v):
        if isinstance(v, str):
            v = v.strip() or 0
        return int(float(v))


class DoubleVar(Variable):
    _default = 0.0

    def _coerce(self, v):
        if isinstance(v, str):
            v = v.strip() or 0
        return float(v)


class BooleanVar(Variable):
    _default = False

    def _coerce(self, v):
        if isinstance(v, str):
            return v.lower() in ("1", "true", "yes", "on")
        return bool(v)


# ---------------------------------------------------------------- base
class Misc:
    _kv = None
    master = None

    def _init_misc(self):
        self._binds = {}
        self._alive = True
        self._kids = []
        self._order = []
        self.children = {}
        self._colw = {}
        self._roww = {}
        self._propagate = True
        self._touch_hooked = False

    # ----- tiempo -----
    def after(self, ms, func=None, *args):
        if func is None:
            end = _time.time() + int(ms) / 1000.0
            while _time.time() < end:
                _check_stop()
                _time.sleep(min(0.05, max(0, end - _time.time())))
            return None
        _st.after_n += 1
        aid = "after#%d" % _st.after_n

        def fire(dt):
            _st.after.pop(aid, None)
            _post(func, *args)

        _st.after[aid] = _Clock.schedule_once(fire, max(0, int(ms)) / 1000.0)
        return aid

    def after_idle(self, func, *args):
        return self.after(0, func, *args)

    def after_cancel(self, aid):
        ev = _st.after.pop(aid, None)
        if ev is not None:
            ev.cancel()

    # ----- bucle -----
    def mainloop(self, n=0):
        mainloop(n)

    def quit(self):
        _st.quit = True

    def update(self):
        root = _st.default_root
        if root is None or not root._alive:
            raise TclError('can\'t invoke "update" command: application has been destroyed')
        _ui(lambda: None)  # deja que Kivy dibuje los cambios pendientes
        _process_events()

    def update_idletasks(self):
        _ui(lambda: None)

    def wait_window(self, window=None):
        window = window or self
        while window._alive:
            _check_stop()
            try:
                fn, a = _st.events.get(timeout=0.05)
            except _queue.Empty:
                continue
            _run_cb(fn, a)

    def wait_variable(self, var):
        old = var.get()
        while var.get() == old:
            _check_stop()
            try:
                fn, a = _st.events.get(timeout=0.05)
            except _queue.Empty:
                continue
            _run_cb(fn, a)

    waitvar = wait_variable

    # ----- información -----
    def winfo_width(self):
        return int(self._kv.width / _dp(1)) if self._kv is not None else 1

    def winfo_height(self):
        return int(self._kv.height / _dp(1)) if self._kv is not None else 1

    def winfo_reqwidth(self):
        return int(_ui(self._req)[0] / _dp(1))

    def winfo_reqheight(self):
        return int(_ui(self._req)[1] / _dp(1))

    def winfo_screenwidth(self):
        return int(_Window.width / _dp(1))

    def winfo_screenheight(self):
        return int(_Window.height / _dp(1))

    def winfo_x(self):
        return 0

    winfo_y = winfo_rootx = winfo_rooty = winfo_x

    def winfo_exists(self):
        return 1 if self._alive else 0

    def winfo_children(self):
        return list(self._kids)

    def winfo_toplevel(self):
        return _toplevel(self)

    def winfo_ismapped(self):
        return 1 if self._kv is not None and self._kv.parent is not None else 0

    def winfo_viewable(self):
        return self.winfo_ismapped()

    def winfo_class(self):
        return type(self).__name__

    def winfo_pointerxy(self):
        return (0, 0)

    def focus_set(self):
        kv = self._focus_target()
        if kv is not None:
            _later(setattr, kv, "focus", True)

    focus = focus_force = focus_set

    def focus_get(self):
        return None

    def _focus_target(self):
        return None

    def grab_set(self):
        pass

    grab_release = grab_set_global = grab_set

    def bell(self):
        pass

    def option_add(self, *a, **k):
        pass

    def tk_setPalette(self, *a, **k):
        pass

    def clipboard_clear(self):
        from kivy.core.clipboard import Clipboard
        _later(Clipboard.copy, "")

    def clipboard_append(self, text):
        from kivy.core.clipboard import Clipboard
        _later(Clipboard.copy, str(text))

    def clipboard_get(self):
        from kivy.core.clipboard import Clipboard
        return _ui(Clipboard.paste)

    def register(self, func, *a):
        return func

    def nametowidget(self, name):
        return name

    # ----- eventos -----
    def bind(self, sequence=None, func=None, add=None):
        if sequence is None:
            return list(self._binds)
        seq = _norm_seq(sequence)
        if func is None:
            return self._binds.get(seq)
        if add:
            self._binds.setdefault(seq, []).append(func)
        else:
            self._binds[seq] = [func]
        _later(self._hook_event, seq)
        return "bind%d" % id(func)

    def bind_all(self, sequence=None, func=None, add=None):
        return _toplevel(self).bind(sequence, func, add)

    bind_class = lambda self, cls, seq=None, func=None, add=None: self.bind(seq, func, add)

    def unbind(self, sequence, funcid=None):
        self._binds.pop(_norm_seq(sequence), None)

    unbind_all = unbind

    def event_generate(self, sequence, **kw):
        self._fire(_norm_seq(sequence), **kw)

    def _fire(self, seq, **kw):
        for f in self._binds.get(seq, []):
            _post(f, Event(self, type=seq, **kw))

    def _hook_event(self, seq):
        if seq in ("<Button-1>", "<ButtonRelease-1>", "<B1-Motion>", "<Double-Button-1>") \
                and not self._touch_hooked and self._kv is not None:
            self._touch_hooked = True
            self._kv.bind(on_touch_down=self._td, on_touch_move=self._tm, on_touch_up=self._tu)

    def _ev_xy(self, touch):
        kv = self._kv
        return {"x": int((touch.x - kv.x) / _dp(1)), "y": int((kv.top - touch.y) / _dp(1)),
                "x_root": int(touch.x / _dp(1)), "y_root": int((_Window.height - touch.y) / _dp(1))}

    def _td(self, kv, touch):
        if kv.collide_point(*touch.pos):
            touch.ud[id(self)] = True
            if getattr(touch, "is_double_tap", False):
                self._fire("<Double-Button-1>", **self._ev_xy(touch))
            self._fire("<Button-1>", **self._ev_xy(touch))

    def _tm(self, kv, touch):
        if touch.ud.get(id(self)):
            self._fire("<B1-Motion>", **self._ev_xy(touch))

    def _tu(self, kv, touch):
        if touch.ud.get(id(self)):
            self._fire("<ButtonRelease-1>", **self._ev_xy(touch))

    # ----- opciones -----
    def configure(self, cnf=None, **kw):
        if cnf:
            kw = dict(cnf, **kw)
        if not kw:
            return {k: (k, "", "", "", v) for k, v in self._opts.items()}
        kw = _norm_opts(kw)
        self._opts.update(kw)
        if self._kv is not None:
            _ui(self._apply, kw)
            self._relayout()

    config = configure

    def cget(self, key):
        key = _norm_opts({key: None}).popitem()[0]
        v = self._opts.get(key, "")
        if key == "text" and self._kv is not None and hasattr(self._kv, "text") and not isinstance(self, Entry):
            return self._kv.text
        return v

    __getitem__ = cget

    def __setitem__(self, key, value):
        self.configure(**{key: value})

    def keys(self):
        return list(self._opts)

    def _apply(self, kw):
        pass

    # ----- grid de contenedores -----
    def columnconfigure(self, index, cnf=None, **kw):
        kw.update(cnf or {})
        idxs = index if isinstance(index, (list, tuple, range)) else [index]
        for i in idxs:
            if i == "all":
                continue
            self._colw[int(i)] = dict(self._colw.get(int(i), {}), **kw)
        self._relayout()

    def rowconfigure(self, index, cnf=None, **kw):
        kw.update(cnf or {})
        idxs = index if isinstance(index, (list, tuple, range)) else [index]
        for i in idxs:
            self._roww[int(i)] = dict(self._roww.get(int(i), {}), **kw)
        self._relayout()

    grid_columnconfigure = columnconfigure
    grid_rowconfigure = rowconfigure

    def grid_size(self):
        cells = [(k._geom[1]["column"], k._geom[1]["row"]) for k in self._kids if k._geom and k._geom[0] == "grid"]
        if not cells:
            return (0, 0)
        return (max(c for c, r in cells) + 1, max(r for c, r in cells) + 1)

    def grid_slaves(self, row=None, column=None):
        out = []
        for k in self._kids:
            if k._geom and k._geom[0] == "grid":
                o = k._geom[1]
                if (row is None or o["row"] == row) and (column is None or o["column"] == column):
                    out.append(k)
        return out

    def pack_slaves(self):
        return [k for k in self._order if k._geom and k._geom[0] == "pack"]

    slaves = pack_slaves

    def pack_propagate(self, flag=None):
        if flag is None:
            return self._propagate
        self._propagate = _truthy(flag)
        self._relayout()

    grid_propagate = pack_propagate

    def grid_anchor(self, anchor=None):
        pass

    # ----- layout -----
    def _relayout(self):
        top = _toplevel(self)
        if top is not None:
            top._schedule_layout()

    def _register(self, w):
        self._kids.append(w)
        self.children[w._name] = w

    def _unregister(self, w):
        if w in self._kids:
            self._kids.remove(w)
        if w in self._order:
            self._order.remove(w)
        self.children.pop(w._name, None)

    def destroy(self):
        if not self._alive:
            return
        self._alive = False
        for k in list(self._kids):
            k.destroy()
        if self.master is not None:
            self.master._unregister(self)
            self._relayout_master()
        kv = self._kv
        if kv is not None:
            _later(lambda: kv.parent and kv.parent.remove_widget(kv))

    def _relayout_master(self):
        if self.master is not None:
            self.master._relayout()

    def __str__(self):
        return "." + self._name


def _norm_seq(seq):
    s = str(seq)
    aliases = {"<Button>": "<Button-1>", "<1>": "<Button-1>", "<ButtonPress-1>": "<Button-1>",
               "<Enter>": "<Enter>", "<KP_Enter>": "<Return>", "<Key-Return>": "<Return>",
               "<Double-1>": "<Double-Button-1>"}
    return aliases.get(s, s)


_OPT_ALIASES = {"background": "bg", "foreground": "fg", "borderwidth": "bd",
                "activebackground": "activebg", "activeforeground": "activefg"}


def _norm_opts(kw):
    out = {}
    for k, v in kw.items():
        k = k.rstrip("_") if k.endswith("_") and k not in ("from_",) else k
        out[_OPT_ALIASES.get(k, k)] = v
    return out


def _toplevel(w):
    while w is not None and not isinstance(w, Wm):
        w = w.master
    return w


_name_counter = [0]


def _new_name(cls):
    _name_counter[0] += 1
    return "!%s%d" % (cls.lower(), _name_counter[0])


# ---------------------------------------------------------------- geometría
class _Geom:
    """Mixin con pack / grid / place para widgets hijos."""
    _geom = None

    def pack(self, cnf=None, **kw):
        kw.update(cnf or {})
        o = {"side": str(kw.get("side", TOP)).lower(), "fill": str(kw.get("fill", NONE)).lower(),
             "expand": _truthy(kw.get("expand", False)), "padx": _pad(kw.get("padx", 0)),
             "pady": _pad(kw.get("pady", 0)), "ipadx": _px(kw.get("ipadx", 0)),
             "ipady": _px(kw.get("ipady", 0)), "anchor": str(kw.get("anchor", CENTER)).lower()}
        m = self.master
        if self in m._order:
            m._order.remove(self)
        before, after = kw.get("before"), kw.get("after")
        if before in m._order:
            m._order.insert(m._order.index(before), self)
        elif after in m._order:
            m._order.insert(m._order.index(after) + 1, self)
        else:
            m._order.append(self)
        self._geom = ("pack", o)
        self._relayout_master()

    pack_configure = pack

    def grid(self, cnf=None, **kw):
        kw.update(cnf or {})
        old = self._geom[1] if self._geom and self._geom[0] == "grid" else {}
        row = kw.get("row", old.get("row"))
        if row is None:
            rows = [k._geom[1]["row"] for k in self.master._kids if k._geom and k._geom[0] == "grid"]
            row = max(rows) + 1 if rows else 0
        o = {"row": int(row), "column": int(kw.get("column", old.get("column", 0))),
             "rowspan": int(kw.get("rowspan", old.get("rowspan", 1))),
             "columnspan": int(kw.get("columnspan", old.get("columnspan", 1))),
             "sticky": str(kw.get("sticky", old.get("sticky", ""))).lower().replace(",", "").replace(" ", ""),
             "padx": _pad(kw.get("padx", 0)) if "padx" in kw else old.get("padx", (0, 0)),
             "pady": _pad(kw.get("pady", 0)) if "pady" in kw else old.get("pady", (0, 0)),
             "ipadx": _px(kw.get("ipadx", 0)), "ipady": _px(kw.get("ipady", 0))}
        self._geom = ("grid", o)
        self._relayout_master()

    grid_configure = grid

    def place(self, cnf=None, **kw):
        kw.update(cnf or {})
        o = {"x": _px(kw.get("x", 0)), "y": _px(kw.get("y", 0)),
             "relx": float(kw.get("relx", 0)), "rely": float(kw.get("rely", 0)),
             "width": _px(kw["width"]) if "width" in kw else None,
             "height": _px(kw["height"]) if "height" in kw else None,
             "relwidth": float(kw["relwidth"]) if "relwidth" in kw else None,
             "relheight": float(kw["relheight"]) if "relheight" in kw else None,
             "anchor": str(kw.get("anchor", NW)).lower()}
        self._geom = ("place", o)
        self._relayout_master()

    place_configure = place

    def _forget(self):
        self._geom = None
        if self in self.master._order:
            self.master._order.remove(self)
        kv = self._kv
        _later(lambda: kv.parent and kv.parent.remove_widget(kv))
        self._relayout_master()

    pack_forget = grid_forget = place_forget = forget = grid_remove = _forget

    def pack_info(self):
        return dict(self._geom[1]) if self._geom else {}

    grid_info = place_info = pack_info

    def lift(self, *a):
        kv = self._kv

        def do():
            p = kv.parent
            if p is not None:
                p.remove_widget(kv)
                p.add_widget(kv)
        _later(do)

    tkraise = lift

    def lower(self, *a):
        pass


def _anchor_pos(anchor, fx, fy, fw, fh, w, h):
    """Posición (tk, origen arriba-izquierda) de un rectángulo w×h dentro del marco."""
    a = anchor or "center"
    x = fx + (fw - w) / 2
    y = fy + (fh - h) / 2
    if "w" in a:
        x = fx
    if "e" in a:
        x = fx + fw - w
    if "n" in a:
        y = fy
    if "s" in a:
        y = fy + fh - h
    return x, y


class _Container:
    """Mixin para widgets que contienen otros (Tk, Toplevel, Frame...)."""

    def _inner_offset(self):
        """(izq, arriba, der, abajo) que ocupa el propio contenedor (borde, título)."""
        b = _px(self._opts.get("bd", 0)) if self._opts.get("relief", FLAT) != FLAT else 0
        px, py = _px(self._opts.get("padx", 0)), _px(self._opts.get("pady", 0))
        return (b + px, b + py, b + px, b + py)

    def _managed(self, kind):
        if kind == "pack":
            return [k for k in self._order if k._alive and k._geom and k._geom[0] == "pack"]
        return [k for k in self._kids if k._alive and k._geom and k._geom[0] == kind]

    def _req(self):
        l, t, r, b = self._inner_offset()
        w = h = 0
        if self._propagate:
            pw, ph = self._pack_req(self._managed("pack"))
            gw, gh = self._grid_req(self._managed("grid"))
            w, h = max(pw, gw), max(ph, gh)
        if not self._propagate or (w == 0 and h == 0):
            w = _px(self._opts.get("width", 0)) or w
            h = _px(self._opts.get("height", 0)) or h
        return w + l + r, h + t + b

    # ---- pack ----
    def _pack_req(self, kids):
        width = height = maxw = maxh = 0
        for k in kids:
            o = k._geom[1]
            kw, kh = k._req()
            kw += o["ipadx"] * 2 + sum(o["padx"])
            kh += o["ipady"] * 2 + sum(o["pady"])
            if o["side"] in (TOP, BOTTOM):
                maxw = max(maxw, kw + width)
                height += kh
            else:
                maxh = max(maxh, kh + height)
                width += kw
        return max(maxw, width), max(maxh, height)

    def _pack_arrange(self, kids, cx, cy, cw, ch):
        reqs = {}
        for k in kids:
            o = k._geom[1]
            kw, kh = k._req()
            reqs[k] = (kw + o["ipadx"] * 2, kh + o["ipady"] * 2)
        for i, k in enumerate(kids):
            o = k._geom[1]
            kw, kh = reqs[k]
            padw, padh = sum(o["padx"]), sum(o["pady"])
            rest = kids[i:]
            if o["side"] in (TOP, BOTTOM):
                fh = kh + padh
                if o["expand"]:
                    need = sum(reqs[r][1] + sum(r._geom[1]["pady"]) for r in rest if r._geom[1]["side"] in (TOP, BOTTOM))
                    nexp = sum(1 for r in rest if r._geom[1]["expand"] and r._geom[1]["side"] in (TOP, BOTTOM))
                    fh += max(0, ch - need) / max(1, nexp)
                fh = min(fh, ch)
                fx, fw = cx, cw
                if o["side"] == TOP:
                    fy = cy
                    cy += fh
                else:
                    fy = cy + ch - fh
                ch -= fh
            else:
                fw = kw + padw
                if o["expand"]:
                    need = sum(reqs[r][0] + sum(r._geom[1]["padx"]) for r in rest if r._geom[1]["side"] in (LEFT, RIGHT))
                    nexp = sum(1 for r in rest if r._geom[1]["expand"] and r._geom[1]["side"] in (LEFT, RIGHT))
                    fw += max(0, cw - need) / max(1, nexp)
                fw = min(fw, cw)
                fy, fh = cy, ch
                if o["side"] == LEFT:
                    fx = cx
                    cx += fw
                else:
                    fx = cx + cw - fw
                cw -= fw
            ix, iy = fx + o["padx"][0], fy + o["pady"][0]
            iw, ih = max(0, fw - padw), max(0, fh - padh)
            w = iw if o["fill"] in (X, BOTH) else min(kw, iw)
            h = ih if o["fill"] in (Y, BOTH) else min(kh, ih)
            x, y = _anchor_pos(o["anchor"], ix, iy, iw, ih, w, h)
            yield k, x, y, w, h

    # ---- grid ----
    def _grid_dims(self, kids):
        cols, rows = {}, {}
        spans = []
        ncol = nrow = 0
        for k in kids:
            o = k._geom[1]
            kw, kh = k._req()
            kw += sum(o["padx"]) + o["ipadx"] * 2
            kh += sum(o["pady"]) + o["ipady"] * 2
            c, r, cs, rs = o["column"], o["row"], max(1, o["columnspan"]), max(1, o["rowspan"])
            ncol, nrow = max(ncol, c + cs), max(nrow, r + rs)
            if cs == 1:
                cols[c] = max(cols.get(c, 0), kw)
            else:
                spans.append(("c", c, cs, kw))
            if rs == 1:
                rows[r] = max(rows.get(r, 0), kh)
            else:
                spans.append(("r", r, rs, kh))
        for i, o in self._colw.items():
            if i < ncol:
                cols[i] = max(cols.get(i, 0), _px(o.get("minsize", 0)))
        for i, o in self._roww.items():
            if i < nrow:
                rows[i] = max(rows.get(i, 0), _px(o.get("minsize", 0)))
        colw = [cols.get(i, 0) for i in range(ncol)]
        rowh = [rows.get(i, 0) for i in range(nrow)]
        for kind, start, n, size in spans:
            arr = colw if kind == "c" else rowh
            have = sum(arr[start:start + n])
            if have < size:
                for j in range(start, start + n):
                    arr[j] += (size - have) / n
        return colw, rowh

    def _grid_req(self, kids):
        if not kids:
            return 0, 0
        colw, rowh = self._grid_dims(kids)
        return sum(colw), sum(rowh)

    @staticmethod
    def _spread(sizes, avail, weights):
        extra = avail - sum(sizes)
        tw = sum(weights)
        if extra > 0 and tw > 0:
            sizes = [s + extra * w / tw for s, w in zip(sizes, weights)]
        elif extra < 0 and sum(sizes) > 0:
            f = avail / sum(sizes)
            sizes = [s * f for s in sizes]
        return sizes

    def _grid_arrange(self, kids, cx, cy, cw, ch):
        if not kids:
            return
        colw, rowh = self._grid_dims(kids)
        colw = self._spread(colw, cw, [float(self._colw.get(i, {}).get("weight", 0)) for i in range(len(colw))])
        rowh = self._spread(rowh, ch, [float(self._roww.get(i, {}).get("weight", 0)) for i in range(len(rowh))])
        xs = [cx]
        for v in colw:
            xs.append(xs[-1] + v)
        ys = [cy]
        for v in rowh:
            ys.append(ys[-1] + v)
        for k in kids:
            o = k._geom[1]
            c, r = o["column"], o["row"]
            cs, rs = max(1, o["columnspan"]), max(1, o["rowspan"])
            fx, fy = xs[c] + o["padx"][0], ys[r] + o["pady"][0]
            fw = max(0, xs[min(c + cs, len(colw))] - xs[c] - sum(o["padx"]))
            fh = max(0, ys[min(r + rs, len(rowh))] - ys[r] - sum(o["pady"]))
            kw, kh = k._req()
            kw += o["ipadx"] * 2
            kh += o["ipady"] * 2
            st = o["sticky"]
            w = fw if ("e" in st and "w" in st) else min(kw, fw)
            h = fh if ("n" in st and "s" in st) else min(kh, fh)
            anchor = "".join(ch_ for ch_ in "ns" if ch_ in st) + "".join(ch_ for ch_ in "we" if ch_ in st)
            x, y = _anchor_pos(anchor or "center", fx, fy, fw, fh, w, h)
            yield k, x, y, w, h

    # ---- place ----
    def _place_arrange(self, kids, cx, cy, cw, ch):
        for k in kids:
            o = k._geom[1]
            kw, kh = k._req()
            w = o["width"] if o["width"] is not None else (cw * o["relwidth"] if o["relwidth"] is not None else kw)
            h = o["height"] if o["height"] is not None else (ch * o["relheight"] if o["relheight"] is not None else kh)
            ax, ay = cx + o["x"] + cw * o["relx"], cy + o["y"] + ch * o["rely"]
            a = o["anchor"]
            x = ax - (w if "e" in a else 0 if "w" in a else w / 2) if a != NW else ax
            y = ay - (h if "s" in a else 0 if "n" in a else h / 2) if a != NW else ay
            if a == CENTER:
                x, y = ax - w / 2, ay - h / 2
            yield k, x, y, w, h

    def _arrange(self):
        """Coloca a los hijos dentro del rectángulo actual del widget Kivy."""
        kv = self._kv
        l, t, r, b = self._inner_offset()
        cx, cy, cw, ch = l, t, max(0, kv.width - l - r), max(0, kv.height - t - b)
        placed = []
        placed += list(self._pack_arrange(self._managed("pack"), cx, cy, cw, ch))
        placed += list(self._grid_arrange(self._managed("grid"), cx, cy, cw, ch))
        placed += list(self._place_arrange(self._managed("place"), cx, cy, cw, ch))
        for k, x, y, w, h in placed:
            ckv = k._kv
            if ckv.parent is not kv:
                if ckv.parent is not None:
                    ckv.parent.remove_widget(ckv)
                kv.add_widget(ckv)
            ckv.size_hint = (None, None)
            ckv.size = (max(0, w), max(0, h))
            ckv.pos = (kv.x + x, kv.top - y - h)
            if isinstance(k, _Container):
                k._arrange()
            elif hasattr(k, "_after_arrange"):
                k._after_arrange()


# ---------------------------------------------------------------- ventanas
class Wm:
    _visible = True

    def title(self, string=None):
        if string is None:
            return self._title
        self._title = str(string)
        if getattr(self, "_title_lbl", None) is not None:
            _later(setattr, self._title_lbl, "text", self._title)

    wm_title = title

    def geometry(self, newGeometry=None):
        if newGeometry is None:
            return "%dx%d+0+0" % (self.winfo_width(), self.winfo_height())

    wm_geometry = geometry

    def resizable(self, width=None, height=None):
        return None

    def minsize(self, *a):
        pass

    maxsize = aspect = iconbitmap = iconphoto = wm_iconbitmap = wm_iconphoto = minsize
    overrideredirect = transient = positionfrom = sizefrom = iconname = group = minsize
    wm_minsize = wm_maxsize = wm_resizable = wm_transient = wm_overrideredirect = minsize

    def attributes(self, *a, **k):
        return None

    wm_attributes = attributes

    def protocol(self, name=None, func=None):
        self._protocols[name] = func

    wm_protocol = protocol

    def state(self, newstate=None):
        if newstate in ("withdrawn", "iconic"):
            self.withdraw()
        elif newstate == "normal":
            self.deiconify()
        return "normal" if self._visible else "withdrawn"

    wm_state = state

    def withdraw(self):
        self._visible = False
        _later(self._view.dismiss, animation=False)

    iconify = wm_withdraw = withdraw

    def deiconify(self):
        if not self._visible:
            self._visible = True
            _later(self._view.open, animation=False)

    wm_deiconify = deiconify

    def focus_force(self):
        pass

    def _on_close(self):
        handler = self._protocols.get("WM_DELETE_WINDOW")
        _post(handler or self.destroy)


class _WindowBase(Misc, Wm, _Container):
    _is_toplevel = False

    def _init_window(self, master, kw):
        self.master = master
        self._init_misc()
        self._name = _new_name(type(self).__name__)
        self._opts = {"bg": TK_BG}
        self._opts.update(_norm_opts(kw))
        self._title = "tk"
        self._protocols = {}
        self._layout_ev = None
        _ui(self._build_window)
        _st.roots.append(self)

    def _build_window(self):
        top = self._is_toplevel
        view = _KModalView(size_hint=(0.94, 0.9) if top else (1, 1), auto_dismiss=False,
                           background="", background_color=(0, 0, 0, 0),
                           overlay_color=(0, 0, 0, 0.55 if top else 0))
        frame = _KBox(orientation="vertical")
        bar = _KBox(size_hint_y=None, height=_dp(54), padding=(_dp(18), _dp(7), _dp(8), _dp(7)))
        with bar.canvas.before:
            _GColor(1, 1, 1, 1)
            rect = _GRect(pos=bar.pos, size=bar.size)
            _GColor(0, 0, 0, 0.08)
            shadow = _GRect(pos=bar.pos, size=(bar.width, _dp(1)))
        bar.bind(pos=lambda w, v: (setattr(rect, "pos", v), setattr(shadow, "pos", v)),
                 size=lambda w, v: (setattr(rect, "size", v), setattr(shadow, "size", (v[0], _dp(1)))))
        self._title_lbl = _KLabel(text=self._title, color=(0.12, 0.13, 0.16, 1), bold=True, font_size=_sp(17),
                                  halign="left", valign="middle", shorten=True)
        self._title_lbl.bind(size=lambda w, v: setattr(w, "text_size", v))
        close = _TkButton(text="×", size_hint_x=None, width=_dp(46), font_size=_sp(26),
                          fill=_hex("#eef0f3"), color=(0.3, 0.32, 0.36, 1))
        close.bind(state=lambda w, s: setattr(w, "fill", _hex("#e5534b") if s == "down" else _hex("#eef0f3")))
        close.bind(on_release=lambda *a: self._on_close())
        bar.add_widget(self._title_lbl)
        bar.add_widget(close)
        body = _TkPanel(bg=_color(self._opts.get("bg"), _hex(TK_BG)))
        body.bind(size=lambda *a: self._schedule_layout(), pos=lambda *a: self._schedule_layout())
        frame.add_widget(bar)
        frame.add_widget(body)
        view.add_widget(frame)
        self._view = view
        self._kv = body
        _Window.unbind(on_keyboard=_on_back)
        _Window.bind(on_keyboard=_on_back)
        view.open(animation=False)

    def _schedule_layout(self):
        if self._layout_ev is None and self._alive:
            self._layout_ev = _Clock.schedule_once(self._do_layout, 0)

    def _do_layout(self, *a):
        self._layout_ev = None
        if self._alive and self._kv is not None:
            self._arrange()

    def _relayout(self):
        self._schedule_layout()

    def _apply(self, kw):
        if "bg" in kw:
            self._kv.bg = _color(kw["bg"], _hex(TK_BG))

    def destroy(self):
        if not self._alive:
            return
        for k in list(self._kids):
            k.destroy()
        self._alive = False
        if self in _st.roots:
            _st.roots.remove(self)
        view = self._view
        _later(lambda: view.dismiss(animation=False))

    def _inner_offset(self):
        return (0, 0, 0, 0)


class Tk(_WindowBase):
    def __init__(self, screenName=None, baseName=None, className="Tk", useTk=True, sync=False, use=None, **kw):
        self._init_window(None, kw)
        self.tk = self
        if _st.default_root is None or not _st.default_root._alive:
            _st.default_root = self

    def call(self, *a):
        return ""

    def eval(self, s):
        return ""

    def report_callback_exception(self, exc, val, tb):
        _traceback.print_exception(exc, val, tb)


class Toplevel(_WindowBase):
    _is_toplevel = True

    def __init__(self, master=None, cnf=None, **kw):
        kw.update(cnf or {})
        self._init_window(master or _get_default_root(), kw)
        self.tk = self.master


Tcl = Tk


def NoDefaultRoot():
    pass


# ---------------------------------------------------------------- widgets
class Widget(Misc, _Geom):
    _defaults = {}

    def __init__(self, master=None, cnf=None, **kw):
        if master is None:
            master = _get_default_root()
        self.master = master
        self.tk = _toplevel(master)
        self._init_misc()
        self._name = kw.pop("name", None) or _new_name(type(self).__name__)
        self._opts = dict(self._defaults)
        if cnf:
            kw = dict(cnf, **kw)
        self._opts.update(_norm_opts(kw))
        self._var_listener = None
        _ui(self._build)
        master._register(self)

    def _build(self):
        self._kv = self._create()
        self._apply(dict(self._opts))

    def _create(self):
        return _TkPanel()

    def _req(self):
        return _dp(10), _dp(10)

    def _changed(self, *a):
        self._relayout()

    def _bind_var(self, var, setter):
        if self._var_listener is not None and getattr(self, "_bound_var", None) is not None:
            self._bound_var._unlisten(self._var_listener)
        self._bound_var = var
        self._var_listener = setter
        if var is not None:
            var._listen(setter)


def _text_size(kv):
    kv.texture_update()
    return kv.texture_size


def _apply_common(kv, kw, bg_default=None):
    if "fg" in kw and hasattr(kv, "color"):
        kv.color = _color(kw["fg"], [0, 0, 0, 1])
    if "font" in kw:
        for k, v in _font(kw["font"]).items():
            if hasattr(kv, k):
                setattr(kv, k, v)


class Frame(Widget, _Container):
    _defaults = {"bg": None}

    def _create(self):
        return _TkPanel()

    def _apply(self, kw):
        kv = self._kv
        if "bg" in kw:
            kv.bg = _color(kw["bg"]) or [0, 0, 0, 0]
        if "relief" in kw or "bd" in kw or "highlightbackground" in kw:
            relief = self._opts.get("relief", FLAT)
            kv.border = _color(self._opts.get("highlightbackground"), [0.55, 0.55, 0.55, 1]) \
                if relief != FLAT and _px(self._opts.get("bd", 1)) > 0 else [0, 0, 0, 0]

    def _req(self):
        return _Container._req(self)


class LabelFrame(Frame):
    _defaults = {"bg": None, "relief": GROOVE, "bd": 2, "text": ""}

    def _create(self):
        kv = _TkPanel()
        self._lbl = _KLabel(text="", color=(0.1, 0.1, 0.1, 1), font_size=DEFAULT_FS * 0.9, bold=True,
                            size_hint=(None, None))
        kv.add_widget(self._lbl)
        return kv

    def _apply(self, kw):
        Frame._apply(self, kw)
        if "text" in kw:
            self._lbl.text = str(kw["text"])
        _apply_common(self._lbl, kw)
        if "relief" not in self._opts or self._opts.get("relief") != FLAT:
            self._kv.border = [0.6, 0.6, 0.6, 1]

    def _inner_offset(self):
        l, t, r, b = Frame._inner_offset(self)
        th = _text_size(self._lbl)[1] if self._lbl.text else 0
        return (l + _dp(6), t + th + _dp(4), r + _dp(6), b + _dp(6))

    def _arrange(self):
        tw, th = _text_size(self._lbl)
        self._lbl.size = (tw, th)
        self._lbl.pos = (self._kv.x + _dp(8), self._kv.top - th - _dp(2))
        if self._lbl.parent is None:
            self._kv.add_widget(self._lbl)
        _Container._arrange(self)


class Label(Widget):
    _defaults = {"text": "", "anchor": CENTER, "justify": CENTER}

    def _create(self):
        kv = _TkLabel(color=(0, 0, 0, 1), font_size=DEFAULT_FS, halign="center", valign="middle")
        kv.bind(texture_size=self._changed)
        return kv

    def _apply(self, kw):
        kv = self._kv
        if "text" in kw:
            kv.text = str(kw["text"])
        if "textvariable" in kw:
            self._bind_var(kw["textvariable"], lambda v: setattr(kv, "text", str(v)))
        if "bg" in kw:
            kv.bg = _color(kw["bg"]) or [0, 0, 0, 0]
        if "justify" in kw:
            kv.halign = {"left": "left", "right": "right"}.get(str(kw["justify"]), "center")
        if "wraplength" in kw:
            wl = _px(kw["wraplength"])
            kv.text_size = (wl, None) if wl else (None, None)
        if "anchor" in kw:
            a = str(kw["anchor"])
            kv.halign = "left" if "w" in a else "right" if "e" in a else kv.halign
        if "image" in kw and isinstance(kw["image"], PhotoImage):
            kw["image"]._attach(kv)
        _apply_common(kv, kw)

    def _after_arrange(self):
        kv = self._kv
        if not self._opts.get("wraplength"):
            a = str(self._opts.get("anchor", CENTER))
            if "w" in a or "e" in a:
                kv.text_size = (kv.width - _dp(8), None)

    def _req(self):
        tw, th = _text_size(self._kv)
        w = tw + _dp(8) + _px(self._opts.get("padx", 0)) * 2
        h = th + _dp(6) + _px(self._opts.get("pady", 0)) * 2
        if self._opts.get("width"):
            w = float(self._opts["width"]) * self._kv.font_size * 0.6 + _dp(8)
        if self._opts.get("height"):
            h = float(self._opts["height"]) * self._kv.font_size * 1.3 + _dp(6)
        img = self._opts.get("image")
        if isinstance(img, PhotoImage):
            w, h = max(w, _dp(img.width())), max(h, _dp(img.height()))
        return w, h


class Message(Label):
    _defaults = {"text": "", "anchor": CENTER, "justify": LEFT, "wraplength": 260}


class Button(Widget):
    _defaults = {"text": ""}

    def _create(self):
        kv = _TkButton(font_size=DEFAULT_FS, color=(0.12, 0.12, 0.14, 1), halign="center")
        kv.bind(texture_size=self._changed, state=self._press_look,
                on_release=lambda *a: _post(self.invoke_cb))
        return kv

    def _press_look(self, kv, state):
        base = _color(self._opts.get("bg"), _hex(BTN_BG))
        if state == "down":
            active = _color(self._opts.get("activebg"))
            kv.fill = active or [c * 0.82 for c in base[:3]] + [base[3]]
        else:
            kv.fill = base

    def invoke_cb(self):
        if self._opts.get("state", NORMAL) != DISABLED:
            cmd = self._opts.get("command")
            if cmd:
                cmd()

    def invoke(self):
        cmd = self._opts.get("command")
        return cmd() if cmd else None

    def flash(self):
        pass

    def _apply(self, kw):
        kv = self._kv
        if "text" in kw:
            kv.text = str(kw["text"])
        if "textvariable" in kw:
            self._bind_var(kw["textvariable"], lambda v: setattr(kv, "text", str(v)))
        if "bg" in kw:
            kv.fill = _color(kw["bg"], _hex(BTN_BG))
            if "fg" not in self._opts:
                kv.color = _button_fg(kv.fill)
        if "state" in kw:
            kv.disabled = kw["state"] == DISABLED
        if "wraplength" in kw:
            wl = _px(kw["wraplength"])
            kv.text_size = (wl, None) if wl else (None, None)
        _apply_common(kv, kw)

    def _req(self):
        tw, th = _text_size(self._kv)
        w = tw + _dp(22) + _px(self._opts.get("padx", 0)) * 2
        h = max(th + _dp(16), _dp(44)) + _px(self._opts.get("pady", 0)) * 2
        if self._opts.get("width"):
            w = max(float(self._opts["width"]) * self._kv.font_size * 0.6 + _dp(12), _dp(40))
        if self._opts.get("height"):
            h = max(float(self._opts["height"]) * self._kv.font_size * 1.4 + _dp(12), _dp(40))
        return w, h


def _parse_index_tail(s):
    m = _re.search(r"([+-])\s*(\d+)\s*(c|chars?|l|lines?)\s*$", s)
    if not m:
        return s, 0, None
    n = int(m.group(2)) * (1 if m.group(1) == "+" else -1)
    return s[:m.start()].strip(), n, "l" if m.group(3).startswith("l") else "c"


class Entry(Widget):
    _defaults = {"width": 20}

    def _create(self):
        kv = _TkField(multiline=False, font_size=DEFAULT_FS, write_tab=False,
                      text_validate_unfocus=False, padding=(_dp(12), _dp(11)),
                      foreground_color=(0.1, 0.1, 0.12, 1), cursor_color=_hex(ACCENT),
                      cursor_width=_dp(2), selection_color=_hex(ACCENT)[:3] + [0.3])
        kv.bind(text=self._on_text, on_text_validate=lambda *a: self._fire("<Return>", keysym="Return", char="\r"))
        return kv

    def _focus_target(self):
        return self._kv

    def _on_text(self, kv, text):
        var = self._opts.get("textvariable")
        if var is not None:
            var._set_from_ui(text)
        for seq in ("<Key>", "<KeyRelease>", "<KeyPress>"):
            if seq in self._binds:
                self._fire(seq, char=text[-1:] if text else "", keysym=text[-1:] if text else "BackSpace")

    def _apply(self, kw):
        kv = self._kv
        if "textvariable" in kw and kw["textvariable"] is not None:
            self._bind_var(kw["textvariable"], lambda v: kv.text != str(v) and setattr(kv, "text", str(v)))
        if "show" in kw:
            kv.password = bool(kw["show"])
            if kw["show"]:
                kv.password_mask = str(kw["show"])[0]
        if "state" in kw:
            kv.readonly = kw["state"] in (DISABLED, "readonly")
            kv.disabled = kw["state"] == DISABLED
        if "justify" in kw:
            kv.halign = {"right": "right", "center": "center"}.get(str(kw["justify"]), "left")
        if "bg" in kw:
            kv.fill = _color(kw["bg"], [1, 1, 1, 1])
        if "fg" in kw:
            kv.foreground_color = _color(kw["fg"], [0, 0, 0, 1])
        if "insertbackground" in kw:
            kv.cursor_color = _color(kw["insertbackground"], [0, 0, 0, 1])
        if "font" in kw:
            for k, v in _font(kw["font"]).items():
                if k in ("font_size", "font_name"):
                    setattr(kv, k, v)

    def _req(self):
        fs = self._kv.font_size
        return max(float(self._opts.get("width", 20)) * fs * 0.55, _dp(60)) + _dp(16), max(fs * 1.25 + _dp(20), _dp(44))

    def _idx(self, index):
        t = self._kv.text
        if index in (END, "end"):
            return len(t)
        if index in (INSERT, "insert"):
            return self._kv.cursor_index()
        if index in (ANCHOR, SEL_FIRST):
            return min(self._kv.selection_from, self._kv.selection_to)
        if index == SEL_LAST:
            return max(self._kv.selection_from, self._kv.selection_to)
        return max(0, min(len(t), int(index)))

    def get(self):
        return self._kv.text

    def insert(self, index, string):
        def do():
            i = self._idx(index)
            t = self._kv.text
            self._kv.text = t[:i] + str(string) + t[i:]
        _ui(do)

    def delete(self, first, last=None):
        def do():
            a = self._idx(first)
            b = a + 1 if last is None else self._idx(last)
            t = self._kv.text
            self._kv.text = t[:a] + t[max(a, b):]
        _ui(do)

    def icursor(self, index):
        _ui(lambda: setattr(self._kv, "cursor", self._kv.get_cursor_from_index(self._idx(index))))

    def index(self, index):
        return _ui(self._idx, index)

    def select_range(self, start, end):
        _ui(lambda: self._kv.select_text(self._idx(start), self._idx(end)))

    selection_range = select_range

    def select_clear(self):
        _ui(self._kv.cancel_selection)

    selection_clear = select_clear

    def selection_present(self):
        return bool(self._kv.selection_text)

    def xview(self, *a):
        pass

    xview_moveto = xview_scroll = xview


class Spinbox(Entry):
    _defaults = {"width": 10, "from_": 0, "to": 10, "increment": 1}

    def _create(self):
        box = _KBox(spacing=_dp(2))
        self._entry_kv = super()._create()
        minus = _KButton(text="-", size_hint_x=None, width=_dp(44), background_normal="",
                         background_color=_hex("#dcdcdc"), color=(0, 0, 0, 1), font_size=_sp(20))
        plus = _KButton(text="+", size_hint_x=None, width=_dp(44), background_normal="",
                        background_color=_hex("#dcdcdc"), color=(0, 0, 0, 1), font_size=_sp(20))
        minus.bind(on_release=lambda *a: self._step(-1))
        plus.bind(on_release=lambda *a: self._step(1))
        box.add_widget(self._entry_kv)
        box.add_widget(minus)
        box.add_widget(plus)
        self._box = box
        return box

    def _build(self):
        self._kv = self._create()
        self._outer = self._kv
        self._kv = self._entry_kv
        Entry._apply(self, dict(self._opts))
        values = self._opts.get("values")
        if values and not self._kv.text:
            self._kv.text = str(list(values)[0] if not isinstance(values, str) else values.split()[0])
        elif not self._kv.text and self._opts.get("textvariable") is None:
            self._kv.text = str(self._opts.get("from_", self._opts.get("from", 0)))
        self._kv = self._outer

    def _ekv(self):
        return self._entry_kv

    def _step(self, d):
        e = self._entry_kv
        values = self._opts.get("values")
        if values:
            vals = [str(v) for v in (values.split() if isinstance(values, str) else values)]
            i = vals.index(e.text) if e.text in vals else 0
            e.text = vals[max(0, min(len(vals) - 1, i + d))]
        else:
            lo = float(self._opts.get("from_", self._opts.get("from", 0)))
            hi = float(self._opts.get("to", 10))
            inc = float(self._opts.get("increment", 1))
            try:
                v = float(e.text)
            except ValueError:
                v = lo
            v = max(lo, min(hi, v + d * inc))
            e.text = str(int(v)) if v == int(v) and inc == int(inc) else str(round(v, 6))
        _post(self._opts.get("command") or (lambda: None))

    def _on_text(self, kv, text):
        Entry._on_text(self, kv, text)

    def _req(self):
        fs = self._entry_kv.font_size
        return max(float(self._opts.get("width", 10)) * fs * 0.55, _dp(50)) + _dp(104), max(fs * 1.25 + _dp(20), _dp(44))

    def _focus_target(self):
        return self._entry_kv

    def _idx(self, index):
        kv, self._kv = self._kv, self._entry_kv
        try:
            return Entry._idx(self, index)
        finally:
            self._kv = kv

    def get(self):
        return self._entry_kv.text

    def insert(self, index, string):
        def do():
            i = self._idx(index)
            t = self._entry_kv.text
            self._entry_kv.text = t[:i] + str(string) + t[i:]
        _ui(do)

    def delete(self, first, last=None):
        def do():
            a = self._idx(first)
            b = a + 1 if last is None else self._idx(last)
            t = self._entry_kv.text
            self._entry_kv.text = t[:a] + t[max(a, b):]
        _ui(do)

    def _apply(self, kw):
        kv, self._kv = self._kv, self._entry_kv
        try:
            Entry._apply(self, kw)
        finally:
            self._kv = kv


class Text(Widget):
    _defaults = {"width": 40, "height": 10, "wrap": CHAR}

    def _create(self):
        kv = _TkField(multiline=True, font_size=DEFAULT_FS * 0.95, font_name="RobotoMono-Regular",
                      foreground_color=(0.1, 0.1, 0.12, 1), cursor_color=_hex(ACCENT), cursor_width=_dp(2),
                      selection_color=_hex(ACCENT)[:3] + [0.3], padding=(_dp(10), _dp(10)))
        kv.bind(text=self._on_text)
        return kv

    def _on_text(self, kv, text):
        for seq in ("<Key>", "<KeyRelease>", "<KeyPress>", "<<Modified>>"):
            if seq in self._binds:
                self._fire(seq, char=text[-1:] if text else "")

    def _focus_target(self):
        return self._kv

    def _apply(self, kw):
        kv = self._kv
        if "state" in kw:
            kv.readonly = kw["state"] == DISABLED
        if "bg" in kw:
            kv.fill = _color(kw["bg"], [1, 1, 1, 1])
        if "fg" in kw:
            kv.foreground_color = _color(kw["fg"], [0, 0, 0, 1])
        if "insertbackground" in kw:
            kv.cursor_color = _color(kw["insertbackground"], [0, 0, 0, 1])
        if "wrap" in kw:
            kv.do_wrap = kw["wrap"] != NONE
        if "font" in kw:
            for k, v in _font(kw["font"]).items():
                if k in ("font_size", "font_name"):
                    setattr(kv, k, v)

    def _req(self):
        fs = self._kv.font_size
        return float(self._opts.get("width", 40)) * fs * 0.6 + _dp(12), float(self._opts.get("height", 10)) * fs * 1.25 + _dp(12)

    def _idx(self, index):
        t = self._kv.text
        s = str(index).strip()
        s, delta, unit = _parse_index_tail(s)
        lines = t.split("\n")
        if s.startswith("end"):
            pos = len(t) + 1
        elif s.startswith("insert") or s == CURRENT:
            pos = self._kv.cursor_index()
        elif s in (SEL_FIRST, SEL_LAST):
            a, b = sorted((self._kv.selection_from, self._kv.selection_to))
            pos = a if s == SEL_FIRST else b
        else:
            m = _re.match(r"(\d+)\.(\d+|end)", s)
            if not m:
                raise TclError('bad text index "%s"' % index)
            ln = max(1, int(m.group(1)))
            if ln > len(lines):
                return len(t) + 1
            col = len(lines[ln - 1]) if m.group(2) == "end" else min(int(m.group(2)), len(lines[ln - 1]))
            pos = sum(len(x) + 1 for x in lines[:ln - 1]) + col
        if unit == "c":
            pos += delta
        elif unit == "l":
            ln = t[:pos].count("\n") + delta
            col = pos - (t.rfind("\n", 0, pos) + 1)
            ln = max(0, min(len(lines) - 1, ln))
            pos = sum(len(x) + 1 for x in lines[:ln]) + min(col, len(lines[ln]))
        return max(0, min(len(t) + 1, pos))

    def get(self, index1, index2=None):
        def do():
            t = self._kv.text + "\n"
            a = self._idx(index1)
            b = a + 1 if index2 is None else self._idx(index2)
            return t[a:b]
        return _ui(do)

    def insert(self, index, chars, *args):
        def do():
            t = self._kv.text
            i = min(self._idx(index), len(t))
            ro = self._kv.readonly
            self._kv.text = t[:i] + str(chars) + t[i:]
            self._kv.readonly = ro
        _ui(do)

    def delete(self, index1, index2=None):
        def do():
            t = self._kv.text
            a = min(self._idx(index1), len(t))
            b = a + 1 if index2 is None else min(self._idx(index2), len(t))
            self._kv.text = t[:a] + t[max(a, b):]
        _ui(do)

    def replace(self, index1, index2, chars, *args):
        self.delete(index1, index2)
        self.insert(index1, chars)

    def index(self, index):
        def do():
            t = self._kv.text
            pos = min(self._idx(index), len(t) + 1)
            before = (t + "\n")[:pos]
            return "%d.%d" % (before.count("\n") + 1, pos - (before.rfind("\n") + 1))
        return _ui(do)

    def see(self, index):
        def do():
            pos = min(self._idx(index), len(self._kv.text))
            self._kv.cursor = self._kv.get_cursor_from_index(pos)
        _ui(do)

    def mark_set(self, name, index):
        if name == INSERT:
            self.see(index)

    def tag_add(self, *a, **k):
        pass

    tag_configure = tag_config = tag_remove = tag_delete = tag_bind = tag_raise = mark_unset = tag_add

    def tag_ranges(self, *a):
        return ()

    def edit_modified(self, arg=None):
        return False

    def edit_undo(self):
        _ui(self._kv.do_undo)

    def edit_redo(self):
        _ui(self._kv.do_redo)

    def edit_reset(self):
        pass

    edit_separator = edit_reset

    def yview(self, *a):
        if a and a[0] == MOVETO and float(a[1]) >= 1:
            self.see(END)

    yview_moveto = xview = yview

    def yview_pickplace(self, *a):
        pass

    def search(self, pattern, index, stopindex=None, **kw):
        def do():
            t = self._kv.text
            i = t.find(pattern, min(self._idx(index), len(t)))
            if i < 0:
                return ""
            before = t[:i]
            return "%d.%d" % (before.count("\n") + 1, i - (before.rfind("\n") + 1))
        return _ui(do)

    def window_create(self, *a, **k):
        pass

    image_create = window_create


class Checkbutton(Widget):
    _defaults = {"text": "", "onvalue": 1, "offvalue": 0}

    def _create(self):
        box = _KBox(spacing=_dp(4))
        self._cb = _KCheckBox(size_hint_x=None, width=_dp(36), color=(0.1, 0.1, 0.1, 1))
        self._lbl = _TkLabel(color=(0.13, 0.13, 0.15, 1), font_size=DEFAULT_FS, size_hint_x=None)
        self._lbl.bind(texture_size=lambda w, v: (setattr(w, "width", v[0]), self._changed()))
        self._lbl.bind(on_touch_down=lambda w, t: w.collide_point(*t.pos) and setattr(self._cb, "active", not self._cb.active))
        self._cb.bind(active=self._on_active)
        box.add_widget(self._cb)
        box.add_widget(self._lbl)
        self._muting = False
        return box

    def _set_active(self, value):
        self._muting = True
        self._cb.active = value
        self._muting = False

    def _on_active(self, cb, active):
        if self._muting:
            return
        var = self._opts.get("variable")
        if var is not None:
            var._set_from_ui(self._opts.get("onvalue", 1) if active else self._opts.get("offvalue", 0))
        else:
            self._state_value = active
        _post(self._opts.get("command"))

    def _apply(self, kw):
        if "variable" not in self._opts:
            self._opts["variable"] = IntVar()
            kw["variable"] = self._opts["variable"]
        if "text" in kw:
            self._lbl.text = str(kw["text"])
        if "textvariable" in kw:
            self._bind_var(kw["textvariable"], lambda v: setattr(self._lbl, "text", str(v)))
        if "variable" in kw and kw["variable"] is not None:
            var = kw["variable"]
            on = self._opts.get("onvalue", 1)
            var._listen(lambda v: self._set_active(str(v) == str(on) or (v is True and on in (1, True))))
        if "state" in kw:
            self._kv.disabled = kw["state"] == DISABLED
        if "bg" in kw:
            self._lbl.bg = _color(kw["bg"]) or [0, 0, 0, 0]
        _apply_common(self._lbl, kw)

    def _req(self):
        tw, th = _text_size(self._lbl)
        return tw + _dp(48), max(th + _dp(8), _dp(40))

    def select(self):
        _ui(setattr, self._cb, "active", True)

    def deselect(self):
        _ui(setattr, self._cb, "active", False)

    def toggle(self):
        _ui(lambda: setattr(self._cb, "active", not self._cb.active))

    def invoke(self):
        self.toggle()


class Radiobutton(Checkbutton):
    _defaults = {"text": "", "value": ""}

    def _create(self):
        box = super()._create()
        self._cb.allow_no_selection = False
        return box

    def _on_active(self, cb, active):
        if self._muting or not active:
            return
        var = self._opts.get("variable")
        if var is not None:
            var._set_from_ui(self._opts.get("value", ""))
            # refrescar los demás botones del grupo
            for f in list(var._listeners):
                f(var._value)
        _post(self._opts.get("command"))

    def _apply(self, kw):
        if "variable" not in self._opts:
            self._opts["variable"] = StringVar()
            kw["variable"] = self._opts["variable"]
        var = kw.get("variable")
        if var is not None:
            self._cb.group = "radio%d" % id(var)
            kw = dict(kw)
            del kw["variable"]
            var._listen(lambda v: self._set_active(str(v) == str(self._opts.get("value", ""))))
        Checkbutton._apply(self, kw)

    def select(self):
        var = self._opts.get("variable")
        if var is not None:
            var.set(self._opts.get("value", ""))

    def deselect(self):
        _ui(setattr, self._cb, "active", False)

    invoke = select


class Listbox(Widget):
    _defaults = {"width": 20, "height": 10, "selectmode": BROWSE}

    def _create(self):
        self._items = []
        self._sel = set()
        sv = _KScrollView(do_scroll_x=False, bar_width=_dp(4))
        self._list = _KBox(orientation="vertical", size_hint_y=None)
        self._list.bind(minimum_height=self._list.setter("height"))
        sv.add_widget(self._list)
        with sv.canvas.before:
            self._bgc = _GColor(1, 1, 1, 1)
            self._bgr = _GRect()
            _GColor(0.55, 0.55, 0.55, 1)
            self._bline = _GLine(rectangle=(0, 0, 1, 1))
        sv.bind(pos=self._upd_bg, size=self._upd_bg)
        return sv

    def _upd_bg(self, sv, *a):
        self._bgr.pos, self._bgr.size = sv.pos, sv.size
        self._bline.rectangle = (sv.x, sv.y, sv.width, sv.height)

    def _row_h(self):
        return max(self._fs() * 1.9, _dp(40))

    def _fs(self):
        f = _font(self._opts.get("font"))
        return f.get("font_size", DEFAULT_FS)

    def _render(self):
        self._list.clear_widgets()
        sel_bg = _color(self._opts.get("selectbackground"), _hex("#0078d7"))
        bg = _color(self._opts.get("bg"), [1, 1, 1, 1])
        fg = _color(self._opts.get("fg"), [0, 0, 0, 1])
        for i, item in enumerate(self._items):
            on = i in self._sel
            b = _KButton(text=str(item), size_hint_y=None, height=self._row_h(), background_normal="",
                         background_down="", background_color=sel_bg if on else bg,
                         color=(1, 1, 1, 1) if on else fg, halign="left", valign="middle",
                         font_size=self._fs(), padding=(_dp(10), 0))
            b.bind(size=lambda w, v: setattr(w, "text_size", v))
            b.bind(on_release=lambda w, idx=i: self._click(idx))
            self._list.add_widget(b)
        self._bgc.rgba = bg

    def _click(self, i):
        if self._opts.get("state") == DISABLED:
            return
        mode = self._opts.get("selectmode", BROWSE)
        if mode in (MULTIPLE, EXTENDED):
            self._sel ^= {i}
        else:
            self._sel = {i}
        self._render()
        self._fire("<<ListboxSelect>>")

    def _apply(self, kw):
        if "listvariable" in kw and kw["listvariable"] is not None:
            def setter(v):
                if isinstance(v, str):
                    v = v.split()
                self._items = list(v)
                self._render()
            kw["listvariable"]._listen(setter)
        if any(k in kw for k in ("bg", "fg", "font", "selectbackground")):
            self._render()

    def _req(self):
        fs = self._fs()
        return float(self._opts.get("width", 20)) * fs * 0.6 + _dp(12), float(self._opts.get("height", 10)) * self._row_h()

    def _i(self, index):
        if index in (END, "end"):
            return len(self._items)
        if index in (ACTIVE, ANCHOR):
            return min(self._sel) if self._sel else 0
        return int(index)

    def insert(self, index, *elements):
        def do():
            i = self._i(index)
            self._items[i:i] = list(elements)
            self._render()
        _ui(do)

    def delete(self, first, last=None):
        def do():
            a = self._i(first)
            b = a if last is None else min(self._i(last), len(self._items) - 1)
            del self._items[a:b + 1]
            self._sel = {s if s < a else s - (b - a + 1) for s in self._sel if not a <= s <= b}
            self._render()
        _ui(do)

    def get(self, first, last=None):
        if last is None:
            i = self._i(first)
            return self._items[i] if 0 <= i < len(self._items) else ""
        a, b = self._i(first), self._i(last)
        return tuple(self._items[a:b + 1])

    def size(self):
        return len(self._items)

    def curselection(self):
        return tuple(sorted(self._sel))

    def selection_set(self, first, last=None):
        a = self._i(first)
        b = a if last is None else self._i(last)
        self._sel |= set(range(a, b + 1))
        _ui(self._render)

    select_set = selection_set

    def selection_clear(self, first, last=None):
        a = self._i(first)
        b = a if last is None else min(self._i(last), len(self._items))
        self._sel -= set(range(a, b + 1))
        _ui(self._render)

    select_clear = selection_clear

    def selection_includes(self, index):
        return self._i(index) in self._sel

    def activate(self, index):
        pass

    see = nearest = itemconfigure = itemconfig = activate

    def yview(self, *a):
        pass

    xview = yview_moveto = yview


class Scale(Widget):
    _defaults = {"from_": 0, "to": 100, "orient": VERTICAL, "resolution": 1, "showvalue": 1, "label": ""}

    def _create(self):
        box = _KBox(orientation="vertical")
        self._label = _KLabel(color=(0, 0, 0, 1), font_size=DEFAULT_FS * 0.9, size_hint_y=None, height=_dp(22))
        self._slider = _KSlider(cursor_size=(_dp(28), _dp(28)))
        self._slider.bind(value=self._on_value)
        box.add_widget(self._label)
        box.add_widget(self._slider)
        self._muting = False
        return box

    def _fmt(self, v):
        res = float(self._opts.get("resolution", 1))
        return str(int(round(v))) if res >= 1 else str(round(v, 6))

    def _on_value(self, s, v):
        title = self._opts.get("label", "")
        if _truthy(self._opts.get("showvalue", 1)):
            self._label.text = ("%s  %s" % (title, self._fmt(v))).strip()
        else:
            self._label.text = str(title)
        if self._muting:
            return
        var = self._opts.get("variable")
        if var is not None:
            var._set_from_ui(v if float(self._opts.get("resolution", 1)) < 1 else int(round(v)))
        cmd = self._opts.get("command")
        if cmd:
            _post(cmd, self._fmt(v))

    def _apply(self, kw):
        s = self._slider
        lo = float(self._opts.get("from_", self._opts.get("from", 0)))
        hi = float(self._opts.get("to", 100))
        self._muting = True
        s.min, s.max = min(lo, hi), max(lo, hi)
        s.step = float(self._opts.get("resolution", 1))
        s.orientation = "horizontal" if str(self._opts.get("orient", VERTICAL)) == HORIZONTAL else "vertical"
        self._muting = False
        if "variable" in kw and kw["variable"] is not None:
            def setter(v):
                self._muting = True
                try:
                    s.value = float(v)
                finally:
                    self._muting = False
            kw["variable"]._listen(setter)
        if "state" in kw:
            s.disabled = kw["state"] == DISABLED
        self._on_value(s, s.value)

    def _req(self):
        length = _px(self._opts.get("length", 200))
        if str(self._opts.get("orient", VERTICAL)) == HORIZONTAL:
            return length, _dp(70)
        return _dp(70), length

    def get(self):
        v = self._slider.value
        return int(round(v)) if float(self._opts.get("resolution", 1)) >= 1 else v

    def set(self, value):
        _ui(setattr, self._slider, "value", float(value))


class Scrollbar(Widget):
    """Kivy ya desplaza con el dedo: la barra se acepta pero no se dibuja."""

    def _req(self):
        return 0, 0

    def set(self, *a):
        pass

    def get(self):
        return (0.0, 1.0)


class Menu(Widget):
    """Menús de escritorio: se aceptan para que el código no falle."""

    def _req(self):
        return 0, 0

    def add_command(self, *a, **k):
        pass

    add_cascade = add_separator = add_checkbutton = add_radiobutton = add = add_command
    entryconfigure = entryconfig = delete = post = tk_popup = add_command


class Menubutton(Button):
    pass


class OptionMenu(Button):
    def __init__(self, master, variable, value, *values, **kw):
        self._choices = [value] + list(values)
        self._var = variable
        self._cmd = kw.pop("command", None)
        super().__init__(master, text=str(variable.get() or value))
        variable._listen(lambda v: setattr(self._kv, "text", str(v)))
        self._opts["command"] = self._open

    def _open(self):
        choice = _dialog("Elegir", "", [(str(c), c) for c in self._choices], vertical=True)
        if choice is not None:
            self._var.set(choice)
            if self._cmd:
                self._cmd(choice)


class PanedWindow(Frame):
    def add(self, child, **kw):
        child.pack(side=LEFT if self._opts.get("orient") == HORIZONTAL else TOP, fill=BOTH, expand=True)


# ---------------------------------------------------------------- Canvas
class Canvas(Widget):
    _defaults = {"width": 380, "height": 260, "bg": "white"}

    def _create(self):
        self._items = {}
        self._n = 0
        kv = _KStencil()
        kv.bind(pos=self._redraw, size=self._redraw)
        return kv

    def _apply(self, kw):
        self._redraw()

    def _req(self):
        return _px(self._opts.get("width", 380)), _px(self._opts.get("height", 260))

    def _new(self, kind, coords, kw):
        flat = []
        for c in coords:
            if isinstance(c, (list, tuple)):
                for cc in c:
                    flat.extend(cc if isinstance(cc, (list, tuple)) else [cc])
            else:
                flat.append(c)
        self._n += 1
        tags = kw.pop("tags", kw.pop("tag", ()))
        if isinstance(tags, str):
            tags = tags.split()
        self._items[self._n] = {"kind": kind, "coords": [float(v) for v in flat], "opts": kw, "tags": tuple(tags)}
        _later(self._redraw)
        return self._n

    def create_line(self, *coords, **kw):
        return self._new("line", coords, kw)

    def create_rectangle(self, *coords, **kw):
        return self._new("rect", coords, kw)

    def create_oval(self, *coords, **kw):
        return self._new("oval", coords, kw)

    def create_arc(self, *coords, **kw):
        return self._new("arc", coords, kw)

    def create_polygon(self, *coords, **kw):
        return self._new("poly", coords, kw)

    def create_text(self, *coords, **kw):
        return self._new("text", coords, kw)

    def create_image(self, *coords, **kw):
        return self._new("image", coords, kw)

    def create_window(self, *coords, **kw):
        return self._new("window", coords, kw)

    def _find(self, tag_or_id):
        if tag_or_id in (ALL, "all"):
            return list(self._items)
        if isinstance(tag_or_id, int) or (isinstance(tag_or_id, str) and tag_or_id.isdigit()):
            i = int(tag_or_id)
            return [i] if i in self._items else []
        return [i for i, it in self._items.items() if tag_or_id in it["tags"]]

    def find_withtag(self, tag):
        return tuple(self._find(tag))

    def find_all(self):
        return tuple(self._items)

    def find_overlapping(self, x1, y1, x2, y2):
        out = []
        for i, it in self._items.items():
            xs, ys = it["coords"][0::2], it["coords"][1::2]
            if xs and ys and min(xs) <= x2 and max(xs) >= x1 and min(ys) <= y2 and max(ys) >= y1:
                out.append(i)
        return tuple(out)

    def find_closest(self, x, y, *a):
        best, bd = None, None
        for i, it in self._items.items():
            xs, ys = it["coords"][0::2], it["coords"][1::2]
            cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
            d = (cx - x) ** 2 + (cy - y) ** 2
            if bd is None or d < bd:
                best, bd = i, d
        return (best,) if best else ()

    def delete(self, *tags):
        for t in tags:
            for i in self._find(t):
                self._items.pop(i, None)
        _later(self._redraw)

    def coords(self, tag_or_id, *new):
        ids = self._find(tag_or_id)
        if not ids:
            return []
        if new:
            flat = []
            for c in new:
                flat.extend(c if isinstance(c, (list, tuple)) else [c])
            self._items[ids[0]]["coords"] = [float(v) for v in flat]
            _later(self._redraw)
        return list(self._items[ids[0]]["coords"])

    def bbox(self, tag_or_id):
        ids = self._find(tag_or_id)
        if not ids:
            return None
        xs = [x for i in ids for x in self._items[i]["coords"][0::2]]
        ys = [y for i in ids for y in self._items[i]["coords"][1::2]]
        return (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))

    def move(self, tag_or_id, dx, dy):
        for i in self._find(tag_or_id):
            c = self._items[i]["coords"]
            self._items[i]["coords"] = [v + (dx if k % 2 == 0 else dy) for k, v in enumerate(c)]
        _later(self._redraw)

    def moveto(self, tag_or_id, x=None, y=None):
        bb = self.bbox(tag_or_id)
        if bb:
            self.move(tag_or_id, 0 if x is None else float(x) - bb[0], 0 if y is None else float(y) - bb[1])

    def itemconfigure(self, tag_or_id, **kw):
        for i in self._find(tag_or_id):
            self._items[i]["opts"].update(kw)
        _later(self._redraw)

    itemconfig = itemconfigure

    def itemcget(self, tag_or_id, option):
        ids = self._find(tag_or_id)
        return self._items[ids[0]]["opts"].get(option, "") if ids else ""

    def gettags(self, tag_or_id):
        ids = self._find(tag_or_id)
        return self._items[ids[0]]["tags"] if ids else ()

    def addtag_withtag(self, newtag, tag):
        for i in self._find(tag):
            self._items[i]["tags"] += (newtag,)

    def tag_bind(self, tag, sequence=None, func=None, add=None):
        def hit(ev):
            for i in self.find_overlapping(ev.x - 2, ev.y - 2, ev.x + 2, ev.y + 2):
                if i in self._find(tag):
                    return func(ev)
        return self.bind(sequence, hit, add="+")

    def tag_raise(self, tag, *a):
        for i in self._find(tag):
            self._items[i] = self._items.pop(i)
        _later(self._redraw)

    lift = tag_raise

    def tag_lower(self, *a):
        pass

    def type(self, tag_or_id):
        ids = self._find(tag_or_id)
        names = {"rect": "rectangle", "poly": "polygon"}
        return names.get(self._items[ids[0]]["kind"], self._items[ids[0]]["kind"]) if ids else None

    def canvasx(self, x, *a):
        return x

    canvasy = canvasx

    def postscript(self, *a, **k):
        return ""

    def xview(self, *a):
        pass

    yview = xview_moveto = yview_moveto = xview_scroll = yview_scroll = xview

    def _redraw(self, *a):
        kv = self._kv
        if kv is None:
            return
        u = _dp(1)
        X0, TOPY = kv.x, kv.top

        def P(x, y):
            return X0 + x * u, TOPY - y * u

        kv.canvas.clear()
        with kv.canvas:
            _GColor(*(_color(self._opts.get("bg"), [1, 1, 1, 1])))
            _GRect(pos=kv.pos, size=kv.size)
            for it in list(self._items.values()):
                o, c, kind = it["opts"], it["coords"], it["kind"]
                if o.get("state") == HIDDEN:
                    continue
                width = float(o.get("width", 1)) * u
                fill = _color(o.get("fill"), [0, 0, 0, 1] if kind in ("line", "text") else None)
                outline = _color(o.get("outline"), [0, 0, 0, 1] if kind not in ("poly",) else None)
                if kind in ("rect", "oval", "arc") and len(c) >= 4:
                    x1, y1 = P(min(c[0], c[2]), max(c[1], c[3]))
                    x2, y2 = P(max(c[0], c[2]), min(c[1], c[3]))
                    w, h = x2 - x1, y2 - y1
                    if kind == "arc":
                        start = float(o.get("start", 0))
                        extent = float(o.get("extent", 90))
                        a1, a2 = 90 - start - extent, 90 - start
                        if fill:
                            _GColor(*fill)
                            _GEllipse(pos=(x1, y1), size=(w, h), angle_start=a1, angle_end=a2)
                        if outline and float(o.get("width", 1)) > 0:
                            _GColor(*outline)
                            _GLine(ellipse=(x1, y1, w, h, a1, a2), width=width)
                        continue
                    if fill:
                        _GColor(*fill)
                        (_GRect if kind == "rect" else _GEllipse)(pos=(x1, y1), size=(w, h))
                    if outline and float(o.get("width", 1)) > 0:
                        _GColor(*outline)
                        if kind == "rect":
                            _GLine(rectangle=(x1, y1, w, h), width=width)
                        else:
                            _GLine(ellipse=(x1, y1, w, h), width=width)
                elif kind == "line" and len(c) >= 4:
                    pts = []
                    for i in range(0, len(c) - 1, 2):
                        pts.extend(P(c[i], c[i + 1]))
                    _GColor(*fill)
                    _GLine(points=pts, width=max(1, width), cap="round", joint="round")
                elif kind == "poly" and len(c) >= 6:
                    pts = [P(c[i], c[i + 1]) for i in range(0, len(c) - 1, 2)]
                    fill = _color(o.get("fill"), [0, 0, 0, 1])
                    if fill:
                        _GColor(*fill)
                        cx = sum(p[0] for p in pts) / len(pts)
                        cy = sum(p[1] for p in pts) / len(pts)
                        verts = [cx, cy, 0, 0]
                        for p in pts + [pts[0]]:
                            verts += [p[0], p[1], 0, 0]
                        _GMesh(vertices=verts, indices=list(range(len(pts) + 2)), mode="triangle_fan")
                    if outline:
                        _GColor(*outline)
                        _GLine(points=[v for p in pts for v in p], width=width, close=True)
                elif kind == "text" and len(c) >= 2:
                    f = _font(o.get("font")) or {}
                    lbl = _CoreLabel(text=str(o.get("text", "")), font_size=f.get("font_size", DEFAULT_FS),
                                     bold=f.get("bold", False), italic=f.get("italic", False),
                                     font_name=f.get("font_name", "Roboto"))
                    lbl.refresh()
                    tex = lbl.texture
                    if tex is None:
                        continue
                    x, y = P(c[0], c[1])
                    a = str(o.get("anchor", CENTER))
                    tx = x - (0 if "w" in a else tex.width if "e" in a else tex.width / 2)
                    ty = y - (tex.height if "n" in a else 0 if "s" in a else tex.height / 2)
                    _GColor(*fill)
                    _GRect(texture=tex, pos=(tx, ty), size=tex.size)
                elif kind == "image" and isinstance(o.get("image"), PhotoImage):
                    tex = o["image"]._texture()
                    if tex is not None:
                        x, y = P(c[0], c[1])
                        w, h = tex.width * u, tex.height * u
                        a = str(o.get("anchor", CENTER))
                        tx = x - (0 if "w" in a else w if "e" in a else w / 2)
                        ty = y - (h if "n" in a else 0 if "s" in a else h / 2)
                        _GColor(1, 1, 1, 1)
                        _GRect(texture=tex, pos=(tx, ty), size=(w, h))


# ---------------------------------------------------------------- imágenes
class Image:
    pass


class PhotoImage(Image):
    def __init__(self, name=None, cnf=None, master=None, file=None, data=None, width=None, height=None, **kw):
        self.file = file
        self._w, self._h = width, height
        self._tex = None

    def _texture(self):
        if self._tex is None and self.file:
            from kivy.core.image import Image as CoreImage
            try:
                self._tex = CoreImage(self.file).texture
            except Exception:
                self._tex = None
        return self._tex

    def _attach(self, kv):
        tex = _ui(self._texture)
        if tex is not None:
            with kv.canvas.after:
                _GColor(1, 1, 1, 1)
                r = _GRect(texture=tex, size=(_dp(tex.width), _dp(tex.height)))

            def place(*a):
                r.pos = (kv.center_x - r.size[0] / 2, kv.center_y - r.size[1] / 2)
            kv.bind(pos=place, size=place)

    def width(self):
        tex = _ui(self._texture)
        return self._w or (tex.width if tex else 0)

    def height(self):
        tex = _ui(self._texture)
        return self._h or (tex.height if tex else 0)

    def subsample(self, *a):
        return self

    zoom = subsample

    def configure(self, **kw):
        if "file" in kw:
            self.file = kw["file"]
            self._tex = None

    config = configure


BitmapImage = PhotoImage


# ---------------------------------------------------------------- diálogos
def _dialog(title, message, buttons, entry=None, initial="", vertical=False):
    """Muestra un diálogo modal y espera la respuesta (en el hilo del usuario)."""
    box = {}
    done = _threading.Event()

    def build():
        content = _KBox(orientation="vertical", spacing=_dp(14), padding=(_dp(8), _dp(12), _dp(8), _dp(4)))
        if message:
            lbl = _KLabel(text=str(message), halign="left", valign="middle", font_size=_sp(16),
                          color=(0.25, 0.27, 0.31, 1), line_height=1.25)
            lbl.bind(width=lambda w, v: setattr(w, "text_size", (v, None)),
                     texture_size=lambda w, v: setattr(w, "height", v[1] + _dp(6)))
            lbl.size_hint_y = None
            content.add_widget(lbl)
        field = None
        if entry:
            field = _TkField(text=str(initial), multiline=False, size_hint_y=None, height=_dp(50),
                             padding=(_dp(12), _dp(13)), font_size=_sp(16), cursor_color=_hex(ACCENT),
                             input_filter={"int": "int", "float": "float"}.get(entry))
            content.add_widget(field)
        row = _KBox(orientation="vertical" if vertical else "horizontal", spacing=_dp(4), size_hint_y=None,
                    height=(_dp(54) * len(buttons)) if vertical else _dp(54))
        popup = _KPopup(title=str(title), content=content, size_hint=(0.88, None), auto_dismiss=False,
                        title_size=_sp(19), title_color=(0.1, 0.11, 0.14, 1), separator_height=0,
                        background="", background_color=(1, 1, 1, 1), overlay_color=(0, 0, 0, 0.45),
                        title_align="left")

        def choose(value):
            if field is not None and value is not None:
                value = field.text
            box["v"] = value
            popup.dismiss()
            done.set()

        for i, (text, value) in enumerate(buttons):
            primary = i == len(buttons) - 1 and not vertical
            b = _TkButton(text=text, font_size=_sp(16), bold=primary,
                          fill=_hex(ACCENT) if primary else _hex("#eef0f3"),
                          color=(1, 1, 1, 1) if primary else (0.15, 0.16, 0.2, 1))
            b.bind(on_release=lambda w, v=value: choose(v))
            row.add_widget(b)
        content.add_widget(row)

        def fit(*a):
            popup.height = sum(c.height for c in content.children) + _dp(10) * len(content.children) + _dp(80)
        content.bind(minimum_height=fit)
        for c in content.children:
            c.bind(height=fit)
        fit()
        if field is not None:
            field.bind(on_text_validate=lambda *a: choose(field.text))
            _Clock.schedule_once(lambda dt: setattr(field, "focus", True), 0.2)
        popup.open()

    if _is_main():
        build()
        return None
    _ui(build)
    while not done.wait(0.05):
        _check_stop()
    return box.get("v")


# ---------------------------------------------------------------- export
from . import messagebox, simpledialog, ttk, constants, filedialog, font, colorchooser, scrolledtext  # noqa: E402

__all__ = [n for n in dir() if not n.startswith("_") and n not in (
    "messagebox", "simpledialog", "ttk", "constants", "filedialog", "font", "colorchooser", "scrolledtext")]
