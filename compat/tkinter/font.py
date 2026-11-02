"""tkinter.font mínimo."""
NORMAL, ROMAN, BOLD, ITALIC = "normal", "roman", "bold", "italic"


class Font:
    def __init__(self, root=None, font=None, name=None, exists=False, **options):
        self._o = {"family": "Roboto", "size": 10, "weight": NORMAL, "slant": ROMAN}
        if isinstance(font, (tuple, list)):
            for i, k in enumerate(("family", "size")):
                if len(font) > i:
                    self._o[k] = font[i]
            for p in font[2:]:
                if "bold" in str(p):
                    self._o["weight"] = BOLD
                if "italic" in str(p):
                    self._o["slant"] = ITALIC
        self._o.update(options)

    def actual(self, option=None, displayof=None):
        return dict(self._o) if option is None else self._o.get(option)

    cget = actual

    def configure(self, **options):
        self._o.update(options)

    config = configure

    def measure(self, text, displayof=None):
        return int(len(str(text)) * int(self._o["size"]) * 0.75)

    def metrics(self, *options, **kw):
        s = int(self._o["size"])
        m = {"ascent": s, "descent": s // 4, "linespace": int(s * 1.4), "fixed": 0}
        return m[options[0]] if options else m

    def copy(self):
        f = Font()
        f._o = dict(self._o)
        return f


def families(root=None, displayof=None):
    return ("Roboto", "RobotoMono", "Courier", "Arial", "Helvetica")


def names(root=None):
    return ("TkDefaultFont", "TkFixedFont", "TkTextFont")


def nametofont(name, root=None):
    return Font(font=("Courier" if "Fixed" in name else "Roboto", 10))
